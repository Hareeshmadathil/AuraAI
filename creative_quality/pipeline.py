"""Bounded deterministic Content Quality Engine pipeline."""

from __future__ import annotations

from typing import Any

from agents.base_employee import BaseEmployee
from agents.directors import CreativeDirector
from agents.specialists import (
    FactualityReviewer,
    HookArchitect,
    MotionDesigner,
    RetentionAuditor,
    StoryDirector,
    SubtitleDesigner,
    ThumbnailPsychologist,
)
from core import DepartmentName, OperationResult, TaskRecord, utc_now
from creative_quality.intelligence import CreativeQualityIntelligence
from creative_quality.models import (
    CreativeQualityIssue,
    CreativeQualityPackage,
    CreativeQualityPipelineResult,
    CreativeQualityStage,
    CreativeQualityStageResult,
    FactualityReport,
    HookAnalysis,
    MotionPlan,
    QualityDimension,
    QualityGateStatus,
    QualitySeverity,
    RetentionReport,
    RevisionPlan,
    StoryFlowReport,
    SubtitleOptimization,
    ThumbnailQualityReport,
)
from creative_quality.quality_gate import CreativeQualityGateEvaluator
from creative_quality.revision_engine import DeterministicRevisionEngine
from creative_quality.scoring import CreativeQualityScorer
from production.models import ProductionPackage
from runtime_engine.event_bus import RuntimeEventBus
from runtime_engine.models import (
    RuntimeEventSeverity,
    RuntimeEventType,
    RuntimeMode,
)
from runtime_engine.orchestrator import RuntimeOrchestrator
from runtime_engine.state_manager import RuntimeStateManager


class CreativeQualityPipeline:
    """Coordinate director planning, specialist reviews, gate, and revision."""

    _COMPLETION_EVENTS = {
        CreativeQualityStage.HOOK_REVIEW: RuntimeEventType.HOOK_REVIEW_COMPLETED,
        CreativeQualityStage.STORY_REVIEW: RuntimeEventType.STORY_REVIEW_COMPLETED,
        CreativeQualityStage.RETENTION_REVIEW: (
            RuntimeEventType.RETENTION_REVIEW_COMPLETED
        ),
        CreativeQualityStage.MOTION_REVIEW: RuntimeEventType.MOTION_REVIEW_COMPLETED,
        CreativeQualityStage.SUBTITLE_REVIEW: (
            RuntimeEventType.SUBTITLE_REVIEW_COMPLETED
        ),
        CreativeQualityStage.THUMBNAIL_REVIEW: (
            RuntimeEventType.THUMBNAIL_REVIEW_COMPLETED
        ),
        CreativeQualityStage.FACTUALITY_REVIEW: (
            RuntimeEventType.FACTUALITY_REVIEW_COMPLETED
        ),
    }

    def __init__(
        self,
        *,
        creative_director: CreativeDirector,
        hook_architect: HookArchitect,
        story_director: StoryDirector,
        retention_auditor: RetentionAuditor,
        motion_designer: MotionDesigner,
        subtitle_designer: SubtitleDesigner,
        thumbnail_psychologist: ThumbnailPsychologist,
        factuality_reviewer: FactualityReviewer,
        scorer: CreativeQualityScorer,
        gate_evaluator: CreativeQualityGateEvaluator,
        revision_engine: DeterministicRevisionEngine,
        quality_intelligence: CreativeQualityIntelligence | None = None,
        runtime_orchestrator: RuntimeOrchestrator | None = None,
        state_manager: RuntimeStateManager | None = None,
        event_bus: RuntimeEventBus | None = None,
    ) -> None:
        self.creative_director = creative_director
        self.hook_architect = hook_architect
        self.story_director = story_director
        self.retention_auditor = retention_auditor
        self.motion_designer = motion_designer
        self.subtitle_designer = subtitle_designer
        self.thumbnail_psychologist = thumbnail_psychologist
        self.factuality_reviewer = factuality_reviewer
        self.scorer = scorer
        self.gate_evaluator = gate_evaluator
        self.revision_engine = revision_engine
        self.quality_intelligence = (
            quality_intelligence or CreativeQualityIntelligence()
        )
        self.runtime_orchestrator = runtime_orchestrator
        self.state_manager = state_manager or (
            runtime_orchestrator.state_manager
            if runtime_orchestrator is not None
            else RuntimeStateManager(event_bus or RuntimeEventBus())
        )
        self.event_bus = event_bus or (
            runtime_orchestrator.event_bus
            if runtime_orchestrator is not None
            else self.state_manager.event_bus
        )

    @property
    def employees(self) -> tuple[BaseEmployee, ...]:
        return (
            self.creative_director,
            self.hook_architect,
            self.story_director,
            self.retention_auditor,
            self.motion_designer,
            self.subtitle_designer,
            self.thumbnail_psychologist,
            self.factuality_reviewer,
        )

    def run(
        self,
        package: ProductionPackage | dict[str, Any],
        *,
        founder_quality_override: bool = False,
    ) -> OperationResult:
        """Review one production package and apply at most one revision cycle."""

        try:
            production = ProductionPackage.model_validate(package)
        except Exception as error:
            return OperationResult.failure(
                "Creative Quality requires a valid ProductionPackage.",
                error_code="INVALID_PRODUCTION_PACKAGE",
                data={"exception_type": error.__class__.__name__},
            )
        self._prepare_runtime()
        self._emit(
            RuntimeEventType.CREATIVE_QUALITY_STARTED,
            "Creative Quality review started.",
            metadata={"production_package_id": str(production.package_id)},
        )
        stages: list[CreativeQualityStageResult] = []
        reviews: dict[str, Any] = {}

        definitions = (
            (
                self.creative_director,
                CreativeQualityStage.INTAKE,
                "production_package",
                production,
                "review_plan",
            ),
            (
                self.hook_architect,
                CreativeQualityStage.HOOK_REVIEW,
                "video_script",
                production.script,
                "hook_analysis",
            ),
            (
                self.story_director,
                CreativeQualityStage.STORY_REVIEW,
                "video_script",
                production.script,
                "story_report",
            ),
            (
                self.retention_auditor,
                CreativeQualityStage.RETENTION_REVIEW,
                "video_script",
                production.script,
                "retention_report",
            ),
            (
                self.motion_designer,
                CreativeQualityStage.MOTION_REVIEW,
                "storyboard",
                production.storyboard,
                "motion_plan",
            ),
            (
                self.subtitle_designer,
                CreativeQualityStage.SUBTITLE_REVIEW,
                "subtitle_package",
                production.subtitle_package,
                "subtitle_optimization",
            ),
            (
                self.thumbnail_psychologist,
                CreativeQualityStage.THUMBNAIL_REVIEW,
                "thumbnail_plan",
                production.thumbnail_plan,
                "thumbnail_report",
            ),
            (
                self.factuality_reviewer,
                CreativeQualityStage.FACTUALITY_REVIEW,
                "production_package",
                production,
                "factuality_report",
            ),
        )
        for employee, stage, input_key, value, output_key in definitions:
            result = self._run_employee(
                employee,
                stage,
                TaskRecord(
                    title=f"Creative Quality {stage.value}",
                    department=DepartmentName.CREATIVE_QUALITY,
                    input_data={input_key: value},
                ),
                stages,
                output_key,
            )
            if not result.success:
                self._emit(
                    RuntimeEventType.CREATIVE_QUALITY_BLOCKED,
                    f"Creative Quality failed during {stage.value}.",
                    severity=RuntimeEventSeverity.ERROR,
                )
                return OperationResult.failure(
                    "Creative Quality pipeline failed.",
                    error_code="CREATIVE_QUALITY_STAGE_FAILED",
                    data={
                        "stage_results": [
                            item.model_dump(mode="json") for item in stages
                        ],
                        "completed_outputs": reviews,
                    },
                )
            reviews[output_key] = result.data[output_key]

        hook = HookAnalysis.model_validate(reviews["hook_analysis"])
        story = StoryFlowReport.model_validate(reviews["story_report"])
        retention = RetentionReport.model_validate(reviews["retention_report"])
        motion = MotionPlan.model_validate(reviews["motion_plan"])
        subtitles = SubtitleOptimization.model_validate(
            reviews["subtitle_optimization"]
        )
        thumbnail = ThumbnailQualityReport.model_validate(
            reviews["thumbnail_report"]
        )
        factuality = FactualityReport.model_validate(
            reviews["factuality_report"]
        )
        issues = self._build_issues(
            production,
            hook,
            story,
            retention,
            motion,
            subtitles,
            thumbnail,
            factuality,
        )
        scores = self._calculate_scores(
            production,
            hook,
            story,
            retention,
            motion,
            subtitles,
            thumbnail,
            factuality,
        )
        stages.append(
            self._system_stage(
                CreativeQualityStage.SCORING,
                "Creative Quality Scorer",
                f"score:{scores.overall}",
            )
        )
        self._emit(
            RuntimeEventType.CREATIVE_QUALITY_SCORED,
            f"Creative Quality score calculated: {scores.overall}.",
            metadata={"overall_score": scores.overall},
        )
        gate = self.gate_evaluator.evaluate(
            scores,
            issues,
            founder_override=founder_quality_override,
        )
        empty_plan = RevisionPlan(
            actions=[],
            estimated_quality_gain=0,
            revision_count=0,
        )
        current_stage = (
            CreativeQualityStage.PASSED
            if gate.status == QualityGateStatus.PASSED
            else CreativeQualityStage.FAILED
            if gate.status == QualityGateStatus.BLOCKED
            else CreativeQualityStage.APPROVAL
            if gate.status == QualityGateStatus.FOUNDER_OVERRIDE_REQUIRED
            else CreativeQualityStage.REVISION
        )
        quality = CreativeQualityPackage(
            production_package_id=production.package_id,
            hook_analysis=hook,
            story_report=story,
            retention_report=retention,
            motion_plan=motion,
            subtitle_optimization=subtitles,
            thumbnail_report=thumbnail,
            factuality_report=factuality,
            scores=scores,
            score_weights=self.scorer.weights,
            issues=issues,
            gate=gate,
            revision_plan=empty_plan,
            current_stage=current_stage,
            sample_data=production.input.sample_data,
            completed_at=utc_now(),
        )
        revised: ProductionPackage | None = None
        if gate.status == QualityGateStatus.REVISION_REQUIRED:
            revised, plan, applied = self.revision_engine.revise(
                production,
                quality,
                revision_count=0,
            )
            quality = quality.model_copy(
                update={"revision_plan": plan, "applied_revisions": applied}
            )
            stages.append(
                self._system_stage(
                    CreativeQualityStage.REVISION,
                    "Deterministic Revision Engine",
                    f"revision_plan:{plan.plan_id}",
                )
            )
            self._emit(
                RuntimeEventType.REVISION_PLAN_CREATED,
                "One bounded deterministic revision plan was created.",
            )
            self._emit(
                RuntimeEventType.REVISION_APPLIED,
                "Safe deterministic revisions were applied to a package copy.",
            )
        quality = quality.model_copy(
            update={
                "quality_breakdown": self.quality_intelligence.build(quality)
            }
        )
        self.state_manager.register_creative_quality_package(quality)
        self.state_manager.set_health_component(
            "creative_quality_pipeline",
            "degraded" if gate.status == QualityGateStatus.BLOCKED else "operational",
            gate.rationale,
        )
        self._emit_gate(gate.status)
        self._emit(
            RuntimeEventType.CREATIVE_QUALITY_COMPLETED,
            "Creative Quality review completed; publishing is not approved.",
            metadata={"quality_package_id": str(quality.package_id)},
        )
        pipeline_result = CreativeQualityPipelineResult(
            quality_package=quality,
            original_production_package=production,
            revised_production_package=revised,
            stage_results=stages,
            runtime_snapshot=self.state_manager.snapshot().model_dump(mode="json"),
            dashboard_mode="deterministic_quality_review",
        )
        data = {
            "creative_quality_pipeline_result": pipeline_result.model_dump(
                mode="json"
            ),
            "creative_quality_package": quality.model_dump(mode="json"),
        }
        if gate.status == QualityGateStatus.BLOCKED:
            return OperationResult.failure(
                "Creative Quality gate blocked the package.",
                error_code="CREATIVE_QUALITY_BLOCKED",
                data=data,
            )
        return OperationResult.ok(
            "Creative Quality review completed.",
            data=data,
        )

    def _run_employee(
        self,
        employee: BaseEmployee,
        stage: CreativeQualityStage,
        task: TaskRecord,
        stages: list[CreativeQualityStageResult],
        output_key: str,
    ) -> OperationResult:
        started = utc_now()
        if stage == CreativeQualityStage.HOOK_REVIEW:
            self._emit(
                RuntimeEventType.HOOK_REVIEW_STARTED,
                "Hook review started.",
                agent_id=employee.agent_id,
                agent_name=employee.name,
                task_id=task.task_id,
            )
        try:
            employee.accept_task(task)
            result = employee.execute_current_task()
        except Exception as error:
            result = OperationResult.failure(
                "Creative Quality employee lifecycle failed.",
                error_code="CREATIVE_QUALITY_EMPLOYEE_ERROR",
                data={"exception_type": error.__class__.__name__},
            )
        finally:
            if employee.current_task is not None and not employee.has_active_task:
                employee.clear_current_task()
        stages.append(
            CreativeQualityStageResult(
                stage=stage,
                employee_id=employee.agent_id,
                employee_name=employee.name,
                success=result.success,
                output_reference=(
                    f"{output_key}:structured-output"
                    if result.success
                    else f"{stage.value}:failed"
                ),
                started_at=started,
                completed_at=utc_now(),
                error_message=None if result.success else result.message,
            )
        )
        event = self._COMPLETION_EVENTS.get(stage)
        if event is not None:
            self._emit(
                event,
                f"Creative Quality stage completed: {stage.value}.",
                severity=(
                    RuntimeEventSeverity.INFO
                    if result.success
                    else RuntimeEventSeverity.ERROR
                ),
                agent_id=employee.agent_id,
                agent_name=employee.name,
                task_id=task.task_id,
            )
        return result

    def _calculate_scores(
        self,
        production: ProductionPackage,
        hook: HookAnalysis,
        story: StoryFlowReport,
        retention: RetentionReport,
        motion: MotionPlan,
        subtitles: SubtitleOptimization,
        thumbnail: ThumbnailQualityReport,
        factuality: FactualityReport,
    ):
        sections = story.sections
        thumbnail_score = max(item.total_score for item in thumbnail.concepts)
        thumbnail_trust = max(item.trust_score for item in thumbnail.concepts)
        values = {
            QualityDimension.HOOK: (
                hook.first_five_seconds_score + hook.first_fifteen_seconds_score
            )
            / 2,
            QualityDimension.STORY: story.total_story_score,
            QualityDimension.PACING: sum(item.pacing_score for item in sections)
            / len(sections),
            QualityDimension.RETENTION: retention.estimated_average_retention_score,
            QualityDimension.CLARITY: (
                hook.clarity_score
                + sum(item.clarity_score for item in sections) / len(sections)
            )
            / 2,
            QualityDimension.MOTION: motion.visual_rhythm_score,
            QualityDimension.SUBTITLES: subtitles.overall_subtitle_score,
            QualityDimension.THUMBNAIL: thumbnail_score,
            QualityDimension.FACTUALITY: factuality.factuality_score,
            QualityDimension.TRUST: (
                factuality.factuality_score + thumbnail_trust
            )
            / 2,
            QualityDimension.CALL_TO_ACTION: (
                90
                if production.script.call_to_action
                and "guarantee" not in production.script.call_to_action.lower()
                else 45
            ),
            QualityDimension.PRODUCTION_COMPLETENESS: (
                production.quality_report.score_percentage
                if production.quality_report is not None
                else 0
            ),
        }
        return self.scorer.to_scores(values)

    @staticmethod
    def _build_issues(
        production: ProductionPackage,
        hook: HookAnalysis,
        story: StoryFlowReport,
        retention: RetentionReport,
        motion: MotionPlan,
        subtitles: SubtitleOptimization,
        thumbnail: ThumbnailQualityReport,
        factuality: FactualityReport,
    ) -> list[CreativeQualityIssue]:
        issues: list[CreativeQualityIssue] = []
        for text in hook.weaknesses:
            issues.append(
                CreativeQualityIssue(
                    dimension=QualityDimension.HOOK,
                    severity=QualitySeverity.MEDIUM,
                    title="Opening hook needs refinement",
                    description=text,
                    affected_reference=str(hook.analysis_id),
                    remediation=hook.recommendations[0]
                    if hook.recommendations
                    else "Use the reviewed truthful hook.",
                )
            )
        for section in story.sections:
            for text in section.weak_points:
                issues.append(
                    CreativeQualityIssue(
                        dimension=QualityDimension.PACING,
                        severity=QualitySeverity.MEDIUM,
                        title=f"Story issue: {section.section_title}",
                        description=text,
                        affected_reference=str(section.section_id),
                        remediation=section.improvements[0],
                    )
                )
        for risk in retention.risks:
            issues.append(
                CreativeQualityIssue(
                    dimension=QualityDimension.RETENTION,
                    severity=risk.severity,
                    title=f"Heuristic retention risk: {risk.risk_type}",
                    description=risk.explanation,
                    affected_reference=str(risk.section_id or risk.risk_id),
                    remediation=risk.remediation,
                )
            )
        for warning in motion.overload_risks:
            issues.append(
                CreativeQualityIssue(
                    dimension=QualityDimension.MOTION,
                    severity=QualitySeverity.LOW,
                    title="Motion overload risk",
                    description=warning,
                    affected_reference=str(motion.plan_id),
                    remediation="Use one restrained cue and preserve reading time.",
                )
            )
        for line in subtitles.lines:
            for warning in line.warnings:
                issues.append(
                    CreativeQualityIssue(
                        dimension=QualityDimension.SUBTITLES,
                        severity=QualitySeverity.MEDIUM,
                        title=f"Subtitle line {line.segment_index}",
                        description=warning,
                        affected_reference=str(line.segment_index),
                        remediation="Shorten or retime the cue before rendering.",
                    )
                )
        for concept in thumbnail.concepts:
            if concept.clickbait_risk >= 50:
                issues.append(
                    CreativeQualityIssue(
                        dimension=QualityDimension.TRUST,
                        severity=QualitySeverity.HIGH,
                        title="Misleading thumbnail concept",
                        description=concept.weaknesses[0],
                        affected_reference=str(concept.concept_id),
                        remediation=concept.recommendations[0],
                    )
                )
        for claim in factuality.claims:
            if claim.risk_level in {
                QualitySeverity.HIGH,
                QualitySeverity.BLOCKING,
            }:
                issues.append(
                    CreativeQualityIssue(
                        dimension=QualityDimension.FACTUALITY,
                        severity=QualitySeverity.BLOCKING,
                        title="Unsupported high-risk factual claim",
                        description=claim.issue,
                        affected_reference=str(claim.claim_id),
                        remediation=claim.remediation,
                        blocking=True,
                    )
                )
        if production.quality_report is not None:
            for blocker in production.quality_report.blocking_issues:
                issues.append(
                    CreativeQualityIssue(
                        dimension=QualityDimension.PRODUCTION_COMPLETENESS,
                        severity=QualitySeverity.BLOCKING,
                        title="Production quality blocker",
                        description=blocker,
                        affected_reference=str(production.quality_report.report_id),
                        remediation="Resolve the Production quality-control blocker.",
                        blocking=True,
                    )
                )
        return issues

    def _prepare_runtime(self) -> None:
        if self.state_manager.mode == RuntimeMode.STOPPED:
            self.state_manager.start_runtime()
        registered = {
            state.agent_id for state in self.state_manager.list_employee_states()
        }
        for employee in self.employees:
            if employee.agent_id not in registered:
                self.state_manager.register_employee(employee)

    def _emit_gate(self, status: QualityGateStatus) -> None:
        event = {
            QualityGateStatus.PASSED: RuntimeEventType.CREATIVE_QUALITY_PASSED,
            QualityGateStatus.REVISION_REQUIRED: (
                RuntimeEventType.CREATIVE_QUALITY_REVISION_REQUIRED
            ),
            QualityGateStatus.FOUNDER_OVERRIDE_REQUIRED: (
                RuntimeEventType.FOUNDER_QUALITY_REVIEW_REQUIRED
            ),
            QualityGateStatus.BLOCKED: RuntimeEventType.CREATIVE_QUALITY_BLOCKED,
        }[status]
        self._emit(event, f"Creative Quality gate status: {status.value}.")

    def _emit(
        self,
        event_type: RuntimeEventType,
        message: str,
        *,
        severity: RuntimeEventSeverity = RuntimeEventSeverity.INFO,
        **values: Any,
    ) -> None:
        self.event_bus.emit(
            event_type,
            message,
            severity=severity,
            department=DepartmentName.CREATIVE_QUALITY,
            **values,
        )

    @staticmethod
    def _system_stage(
        stage: CreativeQualityStage,
        employee_name: str,
        reference: str,
    ) -> CreativeQualityStageResult:
        now = utc_now()
        return CreativeQualityStageResult(
            stage=stage,
            employee_name=employee_name,
            success=True,
            output_reference=reference,
            started_at=now,
            completed_at=now,
        )


def create_creative_quality_pipeline(
    *,
    runtime_orchestrator: RuntimeOrchestrator | None = None,
    state_manager: RuntimeStateManager | None = None,
    event_bus: RuntimeEventBus | None = None,
    minimum_score: float = 75.0,
) -> CreativeQualityPipeline:
    """Create an isolated deterministic quality pipeline."""

    return CreativeQualityPipeline(
        creative_director=CreativeDirector(),
        hook_architect=HookArchitect(),
        story_director=StoryDirector(),
        retention_auditor=RetentionAuditor(),
        motion_designer=MotionDesigner(),
        subtitle_designer=SubtitleDesigner(),
        thumbnail_psychologist=ThumbnailPsychologist(),
        factuality_reviewer=FactualityReviewer(),
        scorer=CreativeQualityScorer(),
        gate_evaluator=CreativeQualityGateEvaluator(minimum_score),
        revision_engine=DeterministicRevisionEngine(),
        runtime_orchestrator=runtime_orchestrator,
        state_manager=state_manager,
        event_bus=event_bus,
    )
