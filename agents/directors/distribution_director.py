"""Distribution Director for founder-controlled package planning."""

from __future__ import annotations

from uuid import UUID

from agents.base_employee import BaseEmployee
from core import DepartmentName, OperationResult, TaskRecord
from distribution.models import (
    DistributionPlan,
    DistributionTaskAssignment,
)


class DistributionDirector(BaseEmployee):
    """Plan local preparation without approving or publishing content."""

    def __init__(self) -> None:
        super().__init__(
            name="Relay",
            job_title="Distribution Director",
            department=DepartmentName.DISTRIBUTION,
            description=(
                "Coordinates founder-reviewed distribution preparation and "
                "never uploads content."
            ),
        )

    def perform_task(self, task: TaskRecord) -> OperationResult:
        """Create an ordered plan from an explicit source package ID."""

        raw_id = task.input_data.get("source_package_id")
        if raw_id is None:
            return OperationResult.failure(
                "source_package_id is required.",
                error_code="MISSING_DISTRIBUTION_SOURCE",
            )
        try:
            source_id = UUID(str(raw_id))
        except ValueError:
            return OperationResult.failure(
                "source_package_id must be a UUID.",
                error_code="INVALID_DISTRIBUTION_SOURCE",
            )
        plan = DistributionPlan(
            source_package_id=source_id,
            assignments=[
                DistributionTaskAssignment(
                    sequence=1,
                    role="YouTube Distribution Specialist",
                    output_key="youtube_package",
                ),
                DistributionTaskAssignment(
                    sequence=2,
                    role="Short-form Distribution Specialist",
                    output_key="short_form_packages",
                ),
                DistributionTaskAssignment(
                    sequence=3,
                    role="SEO Publisher",
                    output_key="seo_metadata",
                ),
                DistributionTaskAssignment(
                    sequence=4,
                    role="Metadata Specialist",
                    output_key="metadata_package",
                ),
            ],
        )
        return OperationResult.ok(
            "Distribution Director created a local preparation plan.",
            data={
                "distribution_plan": plan.model_dump(mode="json"),
                "generated_tasks": [
                    item.model_dump(mode="json") for item in plan.to_task_records()
                ],
            },
        )
