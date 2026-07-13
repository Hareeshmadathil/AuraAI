"""Retention Auditor employee."""

from agents.base_employee import BaseEmployee
from core import DepartmentName, OperationResult, TaskRecord
from creative_quality.providers import (
    DeterministicCreativeQualityProvider,
    RetentionReviewProvider,
)
from creative_quality.task_inputs import require_model
from production.models import VideoScript


class RetentionAuditor(BaseEmployee):
    """Locate heuristic pacing and likely drop-off risks."""

    def __init__(self, provider: RetentionReviewProvider | None = None) -> None:
        super().__init__(
            name="Insight",
            job_title="Retention Auditor",
            department=DepartmentName.CREATIVE_QUALITY,
            description="Finds heuristic drop-off, repetition, and fatigue risks.",
        )
        self.provider = provider or DeterministicCreativeQualityProvider()

    def perform_task(self, task: TaskRecord) -> OperationResult:
        """Return timestamp-linked heuristic retention findings."""

        script = require_model(task.input_data, "video_script", VideoScript)
        report = self.provider.review_retention(script)
        return OperationResult.ok(
            "Retention Auditor completed heuristic retention review.",
            data={"retention_report": report.model_dump(mode="json")},
        )
