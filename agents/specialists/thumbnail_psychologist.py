"""Thumbnail Psychologist employee."""

from agents.base_employee import BaseEmployee
from core import DepartmentName, OperationResult, TaskRecord
from creative_quality.providers import (
    DeterministicCreativeQualityProvider,
    ThumbnailReviewProvider,
)
from creative_quality.task_inputs import require_model
from production.models import ThumbnailPlan


class ThumbnailPsychologist(BaseEmployee):
    """Compare truthful thumbnail concepts using internal heuristics."""

    def __init__(self, provider: ThumbnailReviewProvider | None = None) -> None:
        super().__init__(
            name="Focus",
            job_title="Thumbnail Psychologist",
            department=DepartmentName.CREATIVE_QUALITY,
            description="Scores truthful thumbnail clarity, curiosity, and trust.",
        )
        self.provider = provider or DeterministicCreativeQualityProvider()

    def perform_task(self, task: TaskRecord) -> OperationResult:
        """Return deterministic scores for every supplied thumbnail concept."""

        plan = require_model(task.input_data, "thumbnail_plan", ThumbnailPlan)
        report = self.provider.review_thumbnail(plan)
        return OperationResult.ok(
            "Thumbnail Psychologist completed deterministic concept review.",
            data={"thumbnail_report": report.model_dump(mode="json")},
        )
