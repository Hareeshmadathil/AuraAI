"""Manual analytics and deterministic learning employees."""

from __future__ import annotations

from agents.base_employee import BaseEmployee
from analytics.models import AnalyticsReport, ManualPerformanceMetrics
from analytics.providers import AnalyticsProvider
from core import DepartmentName, OperationResult, TaskRecord
from distribution.models import DistributionPackage


class AnalyticsEngineer(BaseEmployee):
    """Validate and calculate from manually supplied metrics."""

    def __init__(self, provider: AnalyticsProvider) -> None:
        super().__init__(
            name="Measure",
            job_title="Analytics Engineer",
            department=DepartmentName.ANALYTICS,
            description="Calculates local performance reports from manual metrics.",
        )
        self.provider = provider

    def perform_task(self, task: TaskRecord) -> OperationResult:
        raw = task.input_data.get("metrics")
        if raw is None:
            return OperationResult.failure(
                "metrics are required.",
                error_code="MISSING_MANUAL_METRICS",
            )
        try:
            metrics = ManualPerformanceMetrics.model_validate(raw)
        except Exception as error:
            return OperationResult.failure(
                "Manual metrics are invalid.",
                error_code="INVALID_MANUAL_METRICS",
                data={"exception_type": error.__class__.__name__},
            )
        report = self.provider.analyze(metrics)
        return OperationResult.ok(
            "Manual analytics report created.",
            data={"analytics_report": report.model_dump(mode="json")},
        )


class PerformanceAnalyst(BaseEmployee):
    """Summarize calculated performance without causal claims."""

    def __init__(self) -> None:
        super().__init__(
            name="Benchmark",
            job_title="Performance Analyst",
            department=DepartmentName.ANALYTICS,
            description="Summarizes manual performance data without predictions.",
        )

    def perform_task(self, task: TaskRecord) -> OperationResult:
        raw = task.input_data.get("analytics_report")
        if raw is None:
            return OperationResult.failure(
                "analytics_report is required.",
                error_code="MISSING_ANALYTICS_REPORT",
            )
        try:
            report = AnalyticsReport.model_validate(raw)
        except Exception as error:
            return OperationResult.failure(
                "analytics_report is invalid.",
                error_code="INVALID_ANALYTICS_REPORT",
                data={"exception_type": error.__class__.__name__},
            )
        return OperationResult.ok(
            "Performance observations prepared.",
            data={
                "performance_observations": [
                    *report.observations,
                    f"Engagement rate: {report.engagement_rate:.2f}%.",
                    (
                        "No causal or revenue conclusion is inferred from this "
                        "single manual report."
                    ),
                ]
            },
        )


class LearningEngineer(BaseEmployee):
    """Generate deterministic recommendations without model training."""

    def __init__(self, provider: AnalyticsProvider) -> None:
        super().__init__(
            name="Iterate",
            job_title="Learning Engineer",
            department=DepartmentName.ANALYTICS,
            description="Compares heuristics with manual outcomes deterministically.",
        )
        self.provider = provider

    def perform_task(self, task: TaskRecord) -> OperationResult:
        raw_package = task.input_data.get("distribution_package")
        raw_report = task.input_data.get("analytics_report")
        if raw_package is None or raw_report is None:
            return OperationResult.failure(
                "distribution_package and analytics_report are required.",
                error_code="MISSING_LEARNING_INPUT",
            )
        try:
            package = DistributionPackage.model_validate(raw_package)
            report = AnalyticsReport.model_validate(raw_report)
        except Exception as error:
            return OperationResult.failure(
                "Learning input is invalid.",
                error_code="INVALID_LEARNING_INPUT",
                data={"exception_type": error.__class__.__name__},
            )
        learning = self.provider.learn(package, report)
        return OperationResult.ok(
            "Deterministic learning report created.",
            data={"learning_report": learning.model_dump(mode="json")},
        )
