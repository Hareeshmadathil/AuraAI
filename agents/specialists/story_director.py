"""Story Director employee."""

from agents.base_employee import BaseEmployee
from core import DepartmentName, OperationResult, TaskRecord
from creative_quality.providers import (
    DeterministicCreativeQualityProvider,
    StoryReviewProvider,
)
from creative_quality.task_inputs import require_model
from production.models import VideoScript


class StoryDirector(BaseEmployee):
    """Review narrative structure without rewriting the full script."""

    def __init__(self, provider: StoryReviewProvider | None = None) -> None:
        super().__init__(
            name="Arc",
            job_title="Story Director",
            department=DepartmentName.CREATIVE_QUALITY,
            description=(
                "Reviews narrative structure, pacing, clarity, and transitions."
            ),
        )
        self.provider = provider or DeterministicCreativeQualityProvider()

    def perform_task(self, task: TaskRecord) -> OperationResult:
        """Return a section-complete deterministic story report."""

        script = require_model(task.input_data, "video_script", VideoScript)
        report = self.provider.review_story(script)
        return OperationResult.ok(
            "Story Director completed deterministic story review.",
            data={"story_report": report.model_dump(mode="json")},
        )
