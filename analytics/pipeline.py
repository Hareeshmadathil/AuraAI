"""Manual metrics import and deterministic learning pipelines."""

from __future__ import annotations

from typing import Any

from agents.base_employee import BaseEmployee
from agents.specialists.analytics_specialists import (
    AnalyticsEngineer,
    LearningEngineer,
    PerformanceAnalyst,
)
from analytics.models import AnalyticsReport, LearningReport, ManualPerformanceMetrics
from analytics.providers import AnalyticsProvider, DeterministicAnalyticsProvider
from core import DepartmentName, OperationResult, TaskRecord
from distribution.approval import DistributionApprovalService
from distribution.employee_execution import (
    execute_employee_task,
    register_runtime_employees,
)
from distribution.models import DistributionPackage, PublishingState
from runtime_engine.event_bus import RuntimeEventBus
from runtime_engine.models import RuntimeEventType
from runtime_engine.state_manager import RuntimeStateManager


class AnalyticsPipeline:
    """Import founder-supplied metrics after a confirmed manual upload."""

    def __init__(
        self,
        *,
        analytics_engineer: AnalyticsEngineer,
        performance_analyst: PerformanceAnalyst,
        approval_service: DistributionApprovalService,
        state_manager: RuntimeStateManager | None = None,
        event_bus: RuntimeEventBus | None = None,
    ) -> None:
        self.analytics_engineer = analytics_engineer
        self.performance_analyst = performance_analyst
        self.approval_service = approval_service
        self.state_manager = state_manager or RuntimeStateManager(
            event_bus or RuntimeEventBus()
        )
        self.event_bus = event_bus or self.state_manager.event_bus

    def run(
        self,
        package: DistributionPackage | dict[str, Any],
        metrics: ManualPerformanceMetrics | dict[str, Any],
    ) -> OperationResult:
        """Validate and register one manual analytics submission."""

        try:
            package = DistributionPackage.model_validate(package)
            metrics = ManualPerformanceMetrics.model_validate(metrics)
        except Exception as error:
            return OperationResult.failure(
                "Manual analytics input validation failed.",
                error_code="INVALID_ANALYTICS_INPUT",
                data={"exception_type": error.__class__.__name__},
            )
        if package.publication_status != PublishingState.UPLOADED_MANUALLY:
            return OperationResult.failure(
                "Metrics require a founder-confirmed manual upload.",
                error_code="MANUAL_UPLOAD_REQUIRED",
            )
        if metrics.distribution_package_id != package.package_id:
            return OperationResult.failure(
                "Metrics do not match the Distribution package.",
                error_code="METRICS_PACKAGE_MISMATCH",
            )
        self._prepare_runtime(
            (self.analytics_engineer, self.performance_analyst)
        )
        result = execute_employee_task(
            self.analytics_engineer,
            TaskRecord(
                title="Import founder-supplied performance metrics",
                department=DepartmentName.ANALYTICS,
                input_data={"metrics": metrics},
            ),
        )
        if not result.success:
            return result
        report = AnalyticsReport.model_validate(result.data["analytics_report"])
        analyst_result = execute_employee_task(
            self.performance_analyst,
            TaskRecord(
                title="Interpret manual performance metrics",
                department=DepartmentName.ANALYTICS,
                input_data={"analytics_report": report},
            ),
        )
        updated = self.approval_service.mark_metrics_imported(package)
        self.state_manager.register_distribution_package(updated, replace=True)
        self.state_manager.register_analytics_report(report, replace=True)
        self.event_bus.emit(
            RuntimeEventType.METRICS_IMPORTED,
            "Founder-supplied metrics imported locally.",
            department=DepartmentName.ANALYTICS,
        )
        return OperationResult.ok(
            "Manual metrics imported.",
            data={
                "analytics_report": report.model_dump(mode="json"),
                "distribution_package": updated.model_dump(mode="json"),
                "performance_observations": analyst_result.data.get(
                    "performance_observations", []
                ),
            },
        )

    def _prepare_runtime(self, employees: tuple[BaseEmployee, ...]) -> None:
        register_runtime_employees(self.state_manager, employees)


class LearningPipeline:
    """Create recommendations from quality heuristics and manual metrics."""

    def __init__(
        self,
        *,
        learning_engineer: LearningEngineer,
        state_manager: RuntimeStateManager | None = None,
        event_bus: RuntimeEventBus | None = None,
    ) -> None:
        self.learning_engineer = learning_engineer
        self.state_manager = state_manager or RuntimeStateManager(
            event_bus or RuntimeEventBus()
        )
        self.event_bus = event_bus or self.state_manager.event_bus

    def run(
        self,
        package: DistributionPackage | dict[str, Any],
        report: AnalyticsReport | dict[str, Any],
    ) -> OperationResult:
        """Generate and register one deterministic learning report."""

        try:
            package = DistributionPackage.model_validate(package)
            report = AnalyticsReport.model_validate(report)
        except Exception as error:
            return OperationResult.failure(
                "Learning input validation failed.",
                error_code="INVALID_LEARNING_INPUT",
                data={"exception_type": error.__class__.__name__},
            )
        if report.metrics.distribution_package_id != package.package_id:
            return OperationResult.failure(
                "Analytics report does not match the Distribution package.",
                error_code="LEARNING_PACKAGE_MISMATCH",
            )
        register_runtime_employees(
            self.state_manager,
            (self.learning_engineer,),
        )
        result = execute_employee_task(
            self.learning_engineer,
            TaskRecord(
                title="Generate deterministic performance learning",
                department=DepartmentName.ANALYTICS,
                input_data={
                    "distribution_package": package,
                    "analytics_report": report,
                },
            ),
        )
        if not result.success:
            return result
        learning = LearningReport.model_validate(result.data["learning_report"])
        self.state_manager.register_learning_report(learning, replace=True)
        self.event_bus.emit(
            RuntimeEventType.LEARNING_COMPLETED,
            "Deterministic learning completed without model training.",
            department=DepartmentName.ANALYTICS,
        )
        return OperationResult.ok(
            "Deterministic learning completed.",
            data={"learning_report": learning.model_dump(mode="json")},
        )


def create_analytics_pipelines(
    *,
    state_manager: RuntimeStateManager | None = None,
    event_bus: RuntimeEventBus | None = None,
    provider: AnalyticsProvider | None = None,
) -> tuple[AnalyticsPipeline, LearningPipeline]:
    """Create analytics and learning pipelines sharing explicit state."""

    selected_provider = provider or DeterministicAnalyticsProvider()
    state = state_manager or RuntimeStateManager(event_bus or RuntimeEventBus())
    analytics = AnalyticsPipeline(
        analytics_engineer=AnalyticsEngineer(selected_provider),
        performance_analyst=PerformanceAnalyst(),
        approval_service=DistributionApprovalService(
            state_manager=state,
            event_bus=event_bus,
        ),
        state_manager=state,
        event_bus=event_bus,
    )
    learning = LearningPipeline(
        learning_engineer=LearningEngineer(selected_provider),
        state_manager=state,
        event_bus=event_bus,
    )
    return analytics, learning
