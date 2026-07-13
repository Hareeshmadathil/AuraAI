"""Deterministic founder-controlled distribution preparation pipeline."""

from __future__ import annotations

from typing import Any

from agents.base_employee import BaseEmployee
from agents.directors.distribution_director import DistributionDirector
from agents.specialists.distribution_specialists import (
    MetadataSpecialist,
    SEOPublisher,
    ShortFormDistributionSpecialist,
    YouTubeDistributionSpecialist,
)
from core import DepartmentName, OperationResult, TaskRecord, WorkflowRecord
from creative_quality.models import CreativeQualityPackage
from distribution.models import DistributionPackage, DistributionPlan
from distribution.providers import (
    DeterministicDistributionProvider,
    DistributionProvider,
)
from production.models import ProductionPackage
from runtime_engine.event_bus import RuntimeEventBus
from distribution.employee_execution import (
    execute_employee_task,
    register_runtime_employees,
)
from runtime_engine.models import RuntimeEventType
from runtime_engine.orchestrator import RuntimeOrchestrator
from runtime_engine.state_manager import RuntimeStateManager


class DistributionPipeline:
    """Coordinate local package preparation without external side effects."""

    def __init__(
        self,
        *,
        director: DistributionDirector,
        youtube_specialist: YouTubeDistributionSpecialist,
        short_form_specialist: ShortFormDistributionSpecialist,
        seo_publisher: SEOPublisher,
        metadata_specialist: MetadataSpecialist,
        provider: DistributionProvider,
        runtime_orchestrator: RuntimeOrchestrator | None = None,
        state_manager: RuntimeStateManager | None = None,
        event_bus: RuntimeEventBus | None = None,
    ) -> None:
        self.director = director
        self.youtube_specialist = youtube_specialist
        self.short_form_specialist = short_form_specialist
        self.seo_publisher = seo_publisher
        self.metadata_specialist = metadata_specialist
        self.provider = provider
        self.runtime_orchestrator = runtime_orchestrator
        self.state_manager = state_manager or (
            runtime_orchestrator.state_manager
            if runtime_orchestrator is not None
            else RuntimeStateManager(event_bus or RuntimeEventBus())
        )
        self.event_bus = event_bus or self.state_manager.event_bus

    @property
    def employees(self) -> tuple[BaseEmployee, ...]:
        return (
            self.director,
            self.youtube_specialist,
            self.short_form_specialist,
            self.seo_publisher,
            self.metadata_specialist,
        )

    def run(
        self,
        source: CreativeQualityPackage | ProductionPackage | dict[str, Any],
    ) -> OperationResult:
        """Build and register one local-only distribution package."""

        parsed = self._parse_source(source)
        if isinstance(parsed, OperationResult):
            return parsed
        self._prepare_runtime()
        self.event_bus.emit(
            RuntimeEventType.DISTRIBUTION_STARTED,
            "Local distribution preparation started.",
            department=DepartmentName.DISTRIBUTION,
        )
        director_result = execute_employee_task(
            self.director,
            TaskRecord(
                title="Plan founder-controlled distribution",
                department=DepartmentName.DISTRIBUTION,
                input_data={"source_package_id": str(parsed.package_id)},
            ),
        )
        if not director_result.success:
            return director_result
        plan = DistributionPlan.model_validate(
            director_result.data["distribution_plan"]
        )
        generated_tasks = plan.to_task_records()
        workflow = WorkflowRecord(
            name="Founder-controlled manual distribution preparation",
            description=(
                "Prepare local metadata and checklists without uploading content."
            ),
            task_ids=[task.task_id for task in generated_tasks],
            context={
                "source_package_id": str(parsed.package_id),
                "automatic_publishing": False,
            },
        )
        workflow.mark_running()
        try:
            package = self.provider.prepare_package(parsed)
        except ValueError as error:
            return OperationResult.failure(
                str(error),
                error_code="DISTRIBUTION_SOURCE_NOT_READY",
            )
        specialist_outputs: dict[str, Any] = {}
        for employee in self.employees[1:]:
            result = execute_employee_task(
                employee,
                TaskRecord(
                    title=f"Prepare {employee.job_title} output",
                    department=DepartmentName.DISTRIBUTION,
                    input_data={"distribution_package": package},
                ),
            )
            if not result.success:
                return result
            specialist_outputs.update(result.data)
        self.state_manager.register_distribution_package(package, replace=True)
        workflow.mark_completed()
        self.state_manager.register_workflow(workflow)
        self.state_manager.set_health_component(
            "distribution_pipeline",
            "operational",
            "Local preparation only; no publishing capability is enabled.",
        )
        self.event_bus.emit(
            RuntimeEventType.DISTRIBUTION_COMPLETED,
            "Local distribution package completed; founder review is required.",
            department=DepartmentName.DISTRIBUTION,
        )
        return OperationResult.ok(
            "Distribution package prepared locally.",
            data={
                "distribution_package": package.model_dump(mode="json"),
                "distribution_plan": director_result.data["distribution_plan"],
                "manual_workflow": workflow.model_dump(mode="json"),
                "specialist_outputs": specialist_outputs,
                "runtime_snapshot": self.state_manager.snapshot().model_dump(
                    mode="json"
                ),
            },
        )

    @staticmethod
    def _parse_source(
        source: CreativeQualityPackage | ProductionPackage | dict[str, Any],
    ) -> CreativeQualityPackage | ProductionPackage | OperationResult:
        if isinstance(source, (CreativeQualityPackage, ProductionPackage)):
            return source
        if not isinstance(source, dict):
            return OperationResult.failure(
                "Distribution requires a ProductionPackage or CreativeQualityPackage.",
                error_code="INVALID_DISTRIBUTION_SOURCE",
            )
        try:
            if "gate" in source and "hook_analysis" in source:
                return CreativeQualityPackage.model_validate(source)
            return ProductionPackage.model_validate(source)
        except Exception as error:
            return OperationResult.failure(
                "Distribution source validation failed.",
                error_code="INVALID_DISTRIBUTION_SOURCE",
                data={"exception_type": error.__class__.__name__},
            )

    def _prepare_runtime(self) -> None:
        register_runtime_employees(self.state_manager, self.employees)


def create_distribution_pipeline(
    *,
    runtime_orchestrator: RuntimeOrchestrator | None = None,
    state_manager: RuntimeStateManager | None = None,
    event_bus: RuntimeEventBus | None = None,
    provider: DistributionProvider | None = None,
) -> DistributionPipeline:
    """Create an isolated deterministic Distribution pipeline."""

    return DistributionPipeline(
        director=DistributionDirector(),
        youtube_specialist=YouTubeDistributionSpecialist(),
        short_form_specialist=ShortFormDistributionSpecialist(),
        seo_publisher=SEOPublisher(),
        metadata_specialist=MetadataSpecialist(),
        provider=provider or DeterministicDistributionProvider(),
        runtime_orchestrator=runtime_orchestrator,
        state_manager=state_manager,
        event_bus=event_bus,
    )
