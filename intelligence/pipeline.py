"""Workflow-backed deterministic Intelligence Department pipeline."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from agents.base_employee import BaseEmployee
from agents.directors import SEODirector
from agents.specialists import (
    AudienceAnalyst,
    CompetitorAnalyst,
    RetentionEngineer,
    ThumbnailAnalyst,
    TrendAnalyst,
)
from core import (
    DepartmentName,
    MissionRecord,
    OperationResult,
    TaskRecord,
    ValidationError,
    WorkflowRecord,
)
from intelligence.models import (
    AudiencePersona,
    CompetitorReport,
    HookAnalysis,
    IntelligencePackage,
    SEOReport,
    ThumbnailAnalysis,
    TrendReport,
)
from intelligence.providers import DeterministicIntelligenceProvider
from runtime_engine.event_bus import RuntimeEventBus
from runtime_engine.models import (
    RuntimeEventSeverity,
    RuntimeEventType,
    RuntimeMode,
)
from runtime_engine.state_manager import RuntimeStateManager


class IntelligencePipeline:
    """Run six Intelligence employees through a shared runtime workflow."""

    def __init__(
        self,
        *,
        trend_analyst: TrendAnalyst,
        competitor_analyst: CompetitorAnalyst,
        audience_analyst: AudienceAnalyst,
        seo_director: SEODirector,
        retention_engineer: RetentionEngineer,
        thumbnail_analyst: ThumbnailAnalyst,
        state_manager: RuntimeStateManager,
        event_bus: RuntimeEventBus,
    ) -> None:
        self.trend_analyst = trend_analyst
        self.competitor_analyst = competitor_analyst
        self.audience_analyst = audience_analyst
        self.seo_director = seo_director
        self.retention_engineer = retention_engineer
        self.thumbnail_analyst = thumbnail_analyst
        self.state_manager = state_manager
        self.event_bus = event_bus

    @property
    def employees(self) -> tuple[BaseEmployee, ...]:
        return (
            self.trend_analyst,
            self.competitor_analyst,
            self.audience_analyst,
            self.seo_director,
            self.retention_engineer,
            self.thumbnail_analyst,
        )

    def run(self, source: str | MissionRecord | Any) -> OperationResult:
        """Build a complete typed package from a niche or mission-like result."""

        try:
            niche, mission_id = self._normalize_source(source)
        except ValidationError as error:
            return OperationResult.failure(
                str(error),
                error_code=error.error_code,
                data=error.details,
            )
        self._prepare_runtime()
        workflow = WorkflowRecord(
            name="Intelligence analysis workflow",
            description=f"Deterministic pre-production analysis for {niche}.",
            context={
                "mission_id": str(mission_id) if mission_id else None,
                "niche": niche,
            },
        )
        tasks = self._build_tasks(niche)
        for _, task, _ in tasks:
            workflow.add_task(task.task_id)
        workflow.mark_running()
        self.state_manager.register_workflow(workflow)
        self.state_manager.update_workflow_state(
            workflow.workflow_id,
            status=workflow.status,
            progress_percentage=0.0,
        )
        self.event_bus.emit(
            RuntimeEventType.INTELLIGENCE_STARTED,
            f"Intelligence analysis started: {niche}.",
            mission_id=mission_id,
            workflow_id=workflow.workflow_id,
            department=DepartmentName.INTELLIGENCE,
        )

        outputs: dict[str, Any] = {}
        for index, (employee, task, output_key) in enumerate(tasks, start=1):
            result = self._run_employee(
                employee, task, workflow, mission_id, output_key
            )
            if not result.success:
                workflow.mark_failed(result.message)
                self.state_manager.update_workflow_state(
                    workflow.workflow_id,
                    status=workflow.status,
                    error_message=result.message,
                )
                return OperationResult.failure(
                    "Intelligence pipeline failed.",
                    error_code="INTELLIGENCE_STAGE_FAILED",
                    data={"stage_result": result.model_dump(mode="json")},
                )
            outputs[output_key] = result.data[output_key]
            self.state_manager.update_workflow_state(
                workflow.workflow_id,
                progress_percentage=round(index / len(tasks) * 100, 2),
                current_step_name=employee.job_title,
            )

        workflow.mark_completed()
        self.state_manager.update_workflow_state(
            workflow.workflow_id,
            status=workflow.status,
            progress_percentage=100.0,
            completed_at=workflow.completed_at,
            current_step_name=None,
        )
        package = IntelligencePackage(
            mission_id=mission_id,
            workflow_id=workflow.workflow_id,
            niche=niche,
            trend_report=TrendReport.model_validate(outputs["trend_report"]),
            competitor_report=CompetitorReport.model_validate(
                outputs["competitor_report"]
            ),
            audience_persona=AudiencePersona.model_validate(
                outputs["audience_persona"]
            ),
            seo_report=SEOReport.model_validate(outputs["seo_report"]),
            thumbnail_analysis=ThumbnailAnalysis.model_validate(
                outputs["thumbnail_analysis"]
            ),
            hook_analysis=HookAnalysis.model_validate(outputs["hook_analysis"]),
            warnings=[
                "Deterministic provider output; validate against live evidence "
                "before production or publication."
            ],
        )
        self.state_manager.register_intelligence_package(package)
        self.state_manager.set_health_component(
            "intelligence_pipeline",
            "operational",
            "Deterministic Intelligence package completed.",
        )
        self.event_bus.emit(
            RuntimeEventType.INTELLIGENCE_COMPLETED,
            f"Intelligence package completed: {niche}.",
            mission_id=mission_id,
            workflow_id=workflow.workflow_id,
            department=DepartmentName.INTELLIGENCE,
            metadata={"package_id": str(package.package_id)},
        )
        return OperationResult.ok(
            "Intelligence package completed.",
            data={
                "intelligence_package": package.model_dump(mode="json"),
                "workflow": workflow.model_dump(mode="json"),
                "runtime_snapshot": self.state_manager.snapshot().model_dump(
                    mode="json"
                ),
            },
        )

    def _run_employee(
        self,
        employee: BaseEmployee,
        task: TaskRecord,
        workflow: WorkflowRecord,
        mission_id: UUID | None,
        output_key: str,
    ) -> OperationResult:
        self.event_bus.emit(
            RuntimeEventType.INTELLIGENCE_STAGE_STARTED,
            f"Intelligence stage started: {employee.job_title}.",
            mission_id=mission_id,
            workflow_id=workflow.workflow_id,
            task_id=task.task_id,
            agent_id=employee.agent_id,
            agent_name=employee.name,
            department=DepartmentName.INTELLIGENCE,
            metadata={"output_key": output_key},
        )
        try:
            employee.accept_task(task)
            result = employee.execute_current_task()
        except Exception as error:
            result = OperationResult.failure(
                "Intelligence employee lifecycle failed.",
                error_code="INTELLIGENCE_EMPLOYEE_ERROR",
                data={"exception_type": error.__class__.__name__},
            )
        finally:
            if employee.current_task is not None and not employee.has_active_task:
                employee.clear_current_task()
        self.event_bus.emit(
            (
                RuntimeEventType.INTELLIGENCE_STAGE_COMPLETED
                if result.success
                else RuntimeEventType.INTELLIGENCE_STAGE_FAILED
            ),
            f"Intelligence stage {'completed' if result.success else 'failed'}: "
            f"{employee.job_title}.",
            mission_id=mission_id,
            workflow_id=workflow.workflow_id,
            task_id=task.task_id,
            agent_id=employee.agent_id,
            agent_name=employee.name,
            department=DepartmentName.INTELLIGENCE,
            severity=(
                RuntimeEventSeverity.INFO
                if result.success
                else RuntimeEventSeverity.ERROR
            ),
            metadata={"output_key": output_key},
        )
        return result

    def _prepare_runtime(self) -> None:
        if self.state_manager.mode == RuntimeMode.STOPPED:
            self.state_manager.start_runtime()
        registered = {
            state.agent_id for state in self.state_manager.list_employee_states()
        }
        for employee in self.employees:
            if employee.agent_id not in registered:
                self.state_manager.register_employee(employee)

    def _build_tasks(
        self, niche: str
    ) -> list[tuple[BaseEmployee, TaskRecord, str]]:
        values = (
            (self.trend_analyst, "trend_report"),
            (self.competitor_analyst, "competitor_report"),
            (self.audience_analyst, "audience_persona"),
            (self.seo_director, "seo_report"),
            (self.retention_engineer, "hook_analysis"),
            (self.thumbnail_analyst, "thumbnail_analysis"),
        )
        return [
            (
                employee,
                TaskRecord(
                    title=f"Create {output_key.replace('_', ' ')}",
                    department=DepartmentName.INTELLIGENCE,
                    input_data={"niche": niche},
                ),
                output_key,
            )
            for employee, output_key in values
        ]

    @staticmethod
    def _normalize_source(source: str | MissionRecord | Any) -> tuple[str, UUID | None]:
        if isinstance(source, str):
            if not source.strip():
                raise ValidationError("Intelligence niche cannot be empty.")
            return " ".join(source.split()), None
        if isinstance(source, MissionRecord):
            if not source.is_approved or source.is_terminal:
                raise ValidationError(
                    "Intelligence requires an approved, non-terminal mission."
                )
            niche = source.context.get("selected_niche") or source.title
            if not isinstance(niche, str) or not niche.strip():
                raise ValidationError("Mission does not contain a usable niche.")
            return " ".join(niche.split()), source.mission_id
        selected = getattr(source, "selected_niche", None)
        niche = getattr(selected, "name", None)
        mission_id = getattr(source, "mission_id", None)
        if isinstance(niche, str) and niche.strip():
            return " ".join(niche.split()), mission_id
        raise ValidationError("Unsupported Intelligence pipeline source.")


def create_intelligence_pipeline(
    *,
    state_manager: RuntimeStateManager | None = None,
    event_bus: RuntimeEventBus | None = None,
) -> IntelligencePipeline:
    """Create an isolated deterministic Intelligence pipeline."""

    bus = event_bus or RuntimeEventBus()
    state = state_manager or RuntimeStateManager(bus)
    provider = DeterministicIntelligenceProvider()
    return IntelligencePipeline(
        trend_analyst=TrendAnalyst(provider),
        competitor_analyst=CompetitorAnalyst(provider),
        audience_analyst=AudienceAnalyst(provider),
        seo_director=SEODirector(provider),
        retention_engineer=RetentionEngineer(provider),
        thumbnail_analyst=ThumbnailAnalyst(provider),
        state_manager=state,
        event_bus=bus,
    )
