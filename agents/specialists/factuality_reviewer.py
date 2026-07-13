"""Factuality Reviewer employee."""

from agents.base_employee import BaseEmployee
from core import DepartmentName, OperationResult, TaskRecord
from creative_quality.providers import (
    DeterministicCreativeQualityProvider,
    FactualityReviewProvider,
)
from creative_quality.task_inputs import require_model
from production.models import ProductionPackage


class FactualityReviewer(BaseEmployee):
    """Classify supplied evidence and unsupported claim risks."""

    def __init__(self, provider: FactualityReviewProvider | None = None) -> None:
        super().__init__(
            name="Verity",
            job_title="Factuality Reviewer",
            department=DepartmentName.CREATIVE_QUALITY,
            description="Flags unsupported, absolute, and high-stakes claims.",
        )
        self.provider = provider or DeterministicCreativeQualityProvider()

    def perform_task(self, task: TaskRecord) -> OperationResult:
        """Return offline factuality findings without external verification."""

        package = require_model(
            task.input_data, "production_package", ProductionPackage
        )
        report = self.provider.review_factuality(package)
        return OperationResult.ok(
            "Factuality Reviewer completed offline evidence review.",
            data={"factuality_report": report.model_dump(mode="json")},
        )
