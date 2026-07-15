"""Ordered deterministic content-production pipeline."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel

from agents.base_employee import BaseEmployee
from agents.directors.production_director import ProductionDirector
from agents.specialists.quality_controller import QualityController
from agents.specialists.script_writer import ScriptWriter
from agents.specialists.shorts_editor import ShortsEditor
from agents.specialists.storyboard_artist import StoryboardArtist
from agents.specialists.thumbnail_designer import ThumbnailDesigner
from agents.specialists.video_editor import VideoEditor
from agents.specialists.voice_artist import VoiceArtist
from core import DepartmentName, OperationResult, TaskRecord, utc_now
from production.artifact_store import ArtifactReference, ArtifactStore
from production.models import (
    ContentBrief,
    ProductionApprovalStatus,
    ProductionInput,
    ProductionPackage,
    ProductionPipelineResult,
    ProductionQualityReport,
    ProductionStage,
    ProductionStageResult,
    ShortFormPackage,
    Storyboard,
    SubtitlePackage,
    ThumbnailPlan,
    VideoAssemblyManifest,
    VideoScript,
    VideoScript,
    VisualGenerationPlan,
    VoiceoverPlan,
)
from production.subtitle_engine import SubtitleEngine
from production.visual_plan import VisualPlanBuilder
from runtime_engine.models import (
    RuntimeEventSeverity,
    RuntimeEventType,
    RuntimeMode,
)
from runtime_engine.orchestrator import RuntimeOrchestrator

if TYPE_CHECKING:
    from intelligence.pipeline import IntelligencePipeline


ModelT = TypeVar("ModelT", bound=BaseModel)


class ProductionPipeline:
    """Coordinate production employees and pure deterministic builders."""

    def __init__(
        self,
        production_director: ProductionDirector,
        script_writer: ScriptWriter,
        storyboard_artist: StoryboardArtist,
        voice_artist: VoiceArtist,
        thumbnail_designer: ThumbnailDesigner,
        shorts_editor: ShortsEditor,
        video_editor: VideoEditor,
        quality_controller: QualityController,
        *,
        runtime_orchestrator: RuntimeOrchestrator | None = None,
        artifact_store: ArtifactStore | None = None,
        visual_plan_builder: VisualPlanBuilder | None = None,
        subtitle_engine: SubtitleEngine | None = None,
        intelligence_pipeline: IntelligencePipeline | None = None,
    ) -> None:
        self.production_director = production_director
        self.script_writer = script_writer
        self.storyboard_artist = storyboard_artist
        self.voice_artist = voice_artist
        self.thumbnail_designer = thumbnail_designer
        self.shorts_editor = shorts_editor
        self.video_editor = video_editor
        self.quality_controller = quality_controller
        self.runtime_orchestrator = runtime_orchestrator
        self.artifact_store = artifact_store
        self.visual_plan_builder = visual_plan_builder or VisualPlanBuilder()
        self.subtitle_engine = subtitle_engine or SubtitleEngine()
        self.intelligence_pipeline = intelligence_pipeline

    @property
    def employees(self) -> tuple[BaseEmployee, ...]:
        """Return every employee participating in this pipeline."""

        return (
            self.production_director,
            self.script_writer,
            self.storyboard_artist,
            self.voice_artist,
            self.thumbnail_designer,
            self.shorts_editor,
            self.video_editor,
            self.quality_controller,
        )

    def run(
        self,
        production_input: ProductionInput | dict[str, Any],
        *,
        founder_approved: bool = False,
        controlled_script_revision: VideoScript | None = None,
        preserved_thumbnail_plan: ThumbnailPlan | None = None,
        controlled_subtitle_engine: SubtitleEngine | None = None,
    ) -> OperationResult:
        """Build a review-ready package and stop at required approval."""

        stages: list[ProductionStageResult] = []
        outputs: dict[str, Any] = {}
        try:
            value = ProductionInput.model_validate(production_input)
        except Exception as error:
            return OperationResult.failure(
                "Production input validation failed.",
                error_code="INVALID_PRODUCTION_INPUT",
                data={"exception_type": error.__class__.__name__},
            )
        self._prepare_runtime()

        director_result = self._run_employee(
            ProductionStage.BRIEF,
            self.production_director,
            TaskRecord(
                title="Plan deterministic content production",
                department=DepartmentName.PRODUCTION,
                input_data={"production_input": value},
            ),
            stages,
        )
        if not director_result.success:
            return self._failure(director_result, stages, outputs)
        brief = ContentBrief.model_validate(director_result.data["content_brief"])
        outputs["content_brief"] = brief.model_dump(mode="json")

        script_input: dict[str, Any] = {"content_brief": brief}
        if controlled_script_revision is not None:
            script_input["controlled_script_revision"] = (
                controlled_script_revision
            )
        script_result = self._run_employee(
            ProductionStage.SCRIPT,
            self.script_writer,
            TaskRecord(
                title=(
                    "Apply controlled founder script revision"
                    if controlled_script_revision is not None
                    else "Write deterministic flagship script"
                ),
                department=DepartmentName.PRODUCTION,
                input_data=script_input,
            ),
            stages,
        )
        if not script_result.success:
            return self._failure(script_result, stages, outputs)
        script = VideoScript.model_validate(script_result.data["video_script"])
        outputs["video_script"] = script.model_dump(mode="json")

        storyboard_result = self._run_employee(
            ProductionStage.STORYBOARD,
            self.storyboard_artist,
            TaskRecord(
                title="Create sequential storyboard",
                department=DepartmentName.PRODUCTION,
                input_data={"video_script": script, "content_brief": brief},
            ),
            stages,
        )
        if not storyboard_result.success:
            return self._failure(storyboard_result, stages, outputs)
        storyboard = Storyboard.model_validate(storyboard_result.data["storyboard"])
        outputs["storyboard"] = storyboard.model_dump(mode="json")

        voice_result = self._run_employee(
            ProductionStage.VOICE,
            self.voice_artist,
            TaskRecord(
                title="Plan provider-neutral voiceover",
                department=DepartmentName.PRODUCTION,
                input_data={
                    "video_script": script,
                    "storyboard": storyboard,
                    "language": value.language,
                    "tone": value.tone,
                },
            ),
            stages,
        )
        if not voice_result.success:
            return self._failure(voice_result, stages, outputs)
        voiceover = VoiceoverPlan.model_validate(voice_result.data["voiceover_plan"])
        outputs["voiceover_plan"] = voiceover.model_dump(mode="json")

        visual = self._run_builder(
            ProductionStage.VISUAL,
            "Visual Plan Builder",
            lambda: self.visual_plan_builder.build(storyboard, brief.format),
            stages,
        )
        if isinstance(visual, OperationResult):
            return self._failure(visual, stages, outputs)
        outputs["visual_plan"] = visual.model_dump(mode="json")

        if preserved_thumbnail_plan is None:
            thumbnail_result = self._run_employee(
                ProductionStage.THUMBNAIL,
                self.thumbnail_designer,
                TaskRecord(
                    title="Create thumbnail concepts",
                    department=DepartmentName.PRODUCTION,
                    input_data={"video_script": script, "content_brief": brief},
                ),
                stages,
            )
            if not thumbnail_result.success:
                return self._failure(thumbnail_result, stages, outputs)
            thumbnail = ThumbnailPlan.model_validate(
                thumbnail_result.data["thumbnail_plan"]
            )
        else:
            thumbnail = ThumbnailPlan.model_validate(
                preserved_thumbnail_plan.model_copy(
                    update={"script_id": script.script_id}
                )
            )
            stages.append(
                self._stage_result(
                    ProductionStage.THUMBNAIL,
                    self.thumbnail_designer.name,
                    self.thumbnail_designer.agent_id,
                    True,
                    f"thumbnail-plan:{thumbnail.plan_id}:preserved",
                    warnings=[
                        "The founder revision preserved the approved thumbnail direction."
                    ],
                )
            )
        outputs["thumbnail_plan"] = thumbnail.model_dump(mode="json")

        short_result = self._run_employee(
            ProductionStage.SHORT_FORM,
            self.shorts_editor,
            TaskRecord(
                title="Create cross-platform short-form derivatives",
                department=DepartmentName.PRODUCTION,
                input_data={"video_script": script, "storyboard": storyboard},
            ),
            stages,
        )
        if not short_result.success:
            return self._failure(short_result, stages, outputs)
        short_form = ShortFormPackage.model_validate(
            short_result.data["short_form_package"]
        )
        outputs["short_form_package"] = short_form.model_dump(mode="json")

        subtitles = self._run_builder(
            ProductionStage.SUBTITLES,
            "Subtitle Engine",
            lambda: (controlled_subtitle_engine or self.subtitle_engine).build(
                voiceover
            ),
            stages,
        )
        if isinstance(subtitles, OperationResult):
            return self._failure(subtitles, stages, outputs)
        outputs["subtitle_package"] = subtitles.model_dump(mode="json")

        editor_result = self._run_employee(
            ProductionStage.ASSEMBLY,
            self.video_editor,
            TaskRecord(
                title="Create non-rendered assembly manifest",
                department=DepartmentName.PRODUCTION,
                input_data={
                    "video_script": script,
                    "storyboard": storyboard,
                    "voiceover_plan": voiceover,
                    "visual_plan": visual,
                    "subtitle_package": subtitles,
                    "thumbnail_plan": thumbnail,
                    "video_format": brief.format,
                },
            ),
            stages,
        )
        if not editor_result.success:
            return self._failure(editor_result, stages, outputs)
        manifest = VideoAssemblyManifest.model_validate(
            editor_result.data["assembly_manifest"]
        )
        outputs["assembly_manifest"] = manifest.model_dump(mode="json")

        approval_status = (
            ProductionApprovalStatus.PENDING
            if value.requires_founder_approval and not founder_approved
            else ProductionApprovalStatus.APPROVED
            if value.requires_founder_approval
            else ProductionApprovalStatus.NOT_REQUIRED
        )
        package = ProductionPackage(
            input=value,
            brief=brief,
            script=script,
            storyboard=storyboard,
            voiceover_plan=voiceover,
            visual_plan=visual,
            thumbnail_plan=thumbnail,
            short_form_package=short_form,
            subtitle_package=subtitles,
            assembly_manifest=manifest,
            current_stage=ProductionStage.QUALITY_CONTROL,
            completed_stages=[stage.stage for stage in stages if stage.success],
            approval_status=approval_status,
            warnings=[
                "Structured production package only; no media has been rendered.",
            ],
        )
        quality_result = self._run_employee(
            ProductionStage.QUALITY_CONTROL,
            self.quality_controller,
            TaskRecord(
                title="Review production package quality",
                department=DepartmentName.PRODUCTION,
                input_data={"production_package": package},
            ),
            stages,
        )
        if not quality_result.success:
            return self._failure(quality_result, stages, outputs, package=package)
        report = ProductionQualityReport.model_validate(
            quality_result.data["quality_report"]
        )
        package.quality_report = report
        package.completed_stages = [stage.stage for stage in stages if stage.success]
        if not report.passed:
            package.current_stage = ProductionStage.FAILED
            package.warnings.extend(report.warnings)
            self._mark_health("degraded", "Production quality blockers require remediation.")
            self._register_runtime_package(package)
            return OperationResult.failure(
                "Production quality control found blocking issues.",
                error_code="PRODUCTION_QUALITY_BLOCKED",
                data=self._result_data(stages, outputs, package),
            )

        if approval_status == ProductionApprovalStatus.PENDING:
            package.current_stage = ProductionStage.APPROVAL
            package.warnings.extend(report.warnings)
            stages.append(
                self._stage_result(
                    ProductionStage.APPROVAL,
                    "Founder",
                    None,
                    True,
                    "founder-approval:pending",
                    warnings=["Explicit founder approval remains required."],
                )
            )
        else:
            package.current_stage = ProductionStage.COMPLETED
            package.completed_at = utc_now()
            package.completed_stages = [
                *package.completed_stages,
                ProductionStage.COMPLETED,
            ]
            stages.append(
                self._stage_result(
                    ProductionStage.COMPLETED,
                    "Production Pipeline",
                    None,
                    True,
                    f"production-package:{package.package_id}",
                )
            )
        package.updated_at = utc_now()
        self._register_runtime_package(package)
        artifacts = self._save_artifacts(package)
        self._emit(
            RuntimeEventType.PRODUCTION_PACKAGE_READY,
            "Production package is review-ready; no media was rendered.",
            metadata={
                "package_id": str(package.package_id),
                "current_stage": package.current_stage.value,
                "sample_data": package.input.sample_data,
            },
        )
        self._mark_health("operational", "Production pipeline completed without blockers.")
        final = ProductionPipelineResult(
            package=package,
            stage_results=stages,
            runtime_snapshot=(
                self.runtime_orchestrator.snapshot().model_dump(mode="json")
                if self.runtime_orchestrator is not None
                else None
            ),
            dashboard_mode=(
                "deterministic_sample" if value.sample_data else "deterministic_input"
            ),
            sample_data=value.sample_data,
            completed_at=utc_now(),
        )
        return OperationResult.ok(
            "Production package created and awaiting review."
            if approval_status == ProductionApprovalStatus.PENDING
            else "Production package completed and is review-ready.",
            data={
                "production_pipeline_result": final.model_dump(mode="json"),
                "artifacts": [item.model_dump(mode="json") for item in artifacts],
            },
        )

    def _run_employee(
        self,
        stage: ProductionStage,
        employee: BaseEmployee,
        task: TaskRecord,
        stages: list[ProductionStageResult],
    ) -> OperationResult:
        started = utc_now()
        self._emit(
            RuntimeEventType.PRODUCTION_STAGE_STARTED,
            f"Production stage started: {stage.value}.",
            task_id=task.task_id,
            agent_id=employee.agent_id,
            agent_name=employee.name,
            department=employee.department,
            metadata={"stage": stage.value},
        )
        try:
            employee.accept_task(task)
            result = employee.execute_current_task()
        except Exception as error:
            result = OperationResult.failure(
                "Production employee lifecycle failed.",
                error_code="PRODUCTION_EMPLOYEE_LIFECYCLE_ERROR",
                data={"exception_type": error.__class__.__name__},
            )
        finally:
            if employee.current_task is not None and not employee.has_active_task:
                employee.clear_current_task()
        reference = self._output_reference(stage, result.data)
        stages.append(
            ProductionStageResult(
                stage=stage,
                employee_name=employee.name,
                employee_id=employee.agent_id,
                success=result.success,
                output_reference=reference,
                started_at=started,
                completed_at=utc_now(),
                warnings=[],
                error_message=None if result.success else result.message,
            )
        )
        self._emit(
            RuntimeEventType.PRODUCTION_STAGE_COMPLETED
            if result.success
            else RuntimeEventType.PRODUCTION_STAGE_FAILED,
            f"Production stage {'completed' if result.success else 'failed'}: {stage.value}.",
            task_id=task.task_id,
            agent_id=employee.agent_id,
            agent_name=employee.name,
            department=employee.department,
            severity=(
                RuntimeEventSeverity.INFO
                if result.success
                else RuntimeEventSeverity.ERROR
            ),
            metadata={"stage": stage.value},
        )
        return result

    def _run_builder(
        self,
        stage: ProductionStage,
        name: str,
        builder: Callable[[], ModelT],
        stages: list[ProductionStageResult],
    ) -> ModelT | OperationResult:
        started = utc_now()
        self._emit(
            RuntimeEventType.PRODUCTION_STAGE_STARTED,
            f"Production stage started: {stage.value}.",
            department=DepartmentName.PRODUCTION,
            metadata={"stage": stage.value},
        )
        try:
            output = builder()
        except Exception as error:
            failure = OperationResult.failure(
                f"{name} failed.",
                error_code="PRODUCTION_BUILDER_FAILED",
                data={"exception_type": error.__class__.__name__},
            )
            stages.append(
                ProductionStageResult(
                    stage=stage,
                    employee_name=name,
                    success=False,
                    output_reference=f"{stage.value}:failed",
                    started_at=started,
                    completed_at=utc_now(),
                    error_message=failure.message,
                )
            )
            self._emit(
                RuntimeEventType.PRODUCTION_STAGE_FAILED,
                f"Production stage failed: {stage.value}.",
                department=DepartmentName.PRODUCTION,
                severity=RuntimeEventSeverity.ERROR,
                metadata={"stage": stage.value},
            )
            return failure
        stages.append(
            ProductionStageResult(
                stage=stage,
                employee_name=name,
                success=True,
                output_reference=f"{output.__class__.__name__}:{self._model_id(output)}",
                started_at=started,
                completed_at=utc_now(),
            )
        )
        self._emit(
            RuntimeEventType.PRODUCTION_STAGE_COMPLETED,
            f"Production stage completed: {stage.value}.",
            department=DepartmentName.PRODUCTION,
            metadata={"stage": stage.value},
        )
        return output

    def _prepare_runtime(self) -> None:
        if self.runtime_orchestrator is None:
            return
        if self.runtime_orchestrator.state_manager.mode == RuntimeMode.STOPPED:
            self.runtime_orchestrator.start()
        registered = {
            employee.agent_id
            for employee in self.runtime_orchestrator.list_registered_employees()
        }
        for employee in self.employees:
            if employee.agent_id not in registered:
                self.runtime_orchestrator.register_employee(employee)
                registered.add(employee.agent_id)

    def _failure(
        self,
        failure: OperationResult,
        stages: list[ProductionStageResult],
        outputs: dict[str, Any],
        *,
        package: ProductionPackage | None = None,
    ) -> OperationResult:
        self._mark_health("degraded", failure.message)
        return OperationResult.failure(
            failure.message,
            error_code=failure.error_code or "PRODUCTION_STAGE_FAILED",
            data=self._result_data(stages, outputs, package),
        )

    def _result_data(
        self,
        stages: list[ProductionStageResult],
        outputs: dict[str, Any],
        package: ProductionPackage | None,
    ) -> dict[str, Any]:
        return {
            "stage_results": [stage.model_dump(mode="json") for stage in stages],
            "completed_outputs": outputs,
            "production_package": (
                package.model_dump(mode="json") if package is not None else None
            ),
            "runtime_snapshot": (
                self.runtime_orchestrator.snapshot().model_dump(mode="json")
                if self.runtime_orchestrator is not None
                else None
            ),
        }

    def _save_artifacts(self, package: ProductionPackage) -> list[ArtifactReference]:
        if self.artifact_store is None:
            return []
        prefix = str(package.package_id)
        script_text = "\n\n".join(
            f"{section.title}\n{section.narration}"
            for section in package.script.sections
        )
        return [
            self.artifact_store.save_model(f"{prefix}-package", package),
            self.artifact_store.save_script(f"{prefix}-script", script_text),
            self.artifact_store.save_srt(f"{prefix}-subtitles", package.subtitle_package.srt_text),
            self.artifact_store.save_vtt(f"{prefix}-subtitles", package.subtitle_package.vtt_text),
            self.artifact_store.save_assembly_manifest(
                f"{prefix}-assembly", package.assembly_manifest
            ),
        ]

    def _emit(self, event_type: RuntimeEventType, message: str, **values: Any) -> None:
        if self.runtime_orchestrator is not None:
            self.runtime_orchestrator.event_bus.emit(event_type, message, **values)

    def _mark_health(self, status: str, message: str) -> None:
        if self.runtime_orchestrator is not None:
            self.runtime_orchestrator.state_manager.set_health_component(
                "production_pipeline", status, message
            )

    def _register_runtime_package(self, package: ProductionPackage) -> None:
        """Expose the final truthful package state in the runtime snapshot."""

        if self.runtime_orchestrator is not None:
            self.runtime_orchestrator.state_manager.register_production_package(
                package,
                replace=True,
            )

    @staticmethod
    def _model_id(value: BaseModel) -> str:
        for name in ("plan_id", "package_id", "storyboard_id", "manifest_id"):
            identifier = getattr(value, name, None)
            if identifier is not None:
                return str(identifier)
        return "structured-output"

    @classmethod
    def _output_reference(
        cls,
        stage: ProductionStage,
        data: dict[str, Any],
    ) -> str:
        if not data:
            return f"{stage.value}:no-output"
        first = next(iter(data.values()))
        if isinstance(first, dict):
            for key in ("brief_id", "script_id", "storyboard_id", "plan_id", "manifest_id", "report_id"):
                if key in first:
                    return f"{stage.value}:{first[key]}"
        return f"{stage.value}:structured-output"

    @staticmethod
    def _stage_result(
        stage: ProductionStage,
        employee_name: str,
        employee_id: Any,
        success: bool,
        output_reference: str,
        *,
        warnings: list[str] | None = None,
    ) -> ProductionStageResult:
        now = utc_now()
        return ProductionStageResult(
            stage=stage,
            employee_name=employee_name,
            employee_id=employee_id,
            success=success,
            output_reference=output_reference,
            started_at=now,
            completed_at=now,
            warnings=warnings or [],
        )
