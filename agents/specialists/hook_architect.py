"""Hook Architect employee."""

from agents.base_employee import BaseEmployee
from core import DepartmentName, OperationResult, TaskRecord
from creative_quality.providers import (
    DeterministicCreativeQualityProvider,
    HookReviewProvider,
)
from creative_quality.task_inputs import require_model
from production.models import VideoScript


class HookArchitect(BaseEmployee):
    """Review and improve truthful opening hooks."""

    def __init__(self, provider: HookReviewProvider | None = None) -> None:
        super().__init__(
            name="Pulse",
            job_title="Hook Architect",
            department=DepartmentName.CREATIVE_QUALITY,
            description="Reviews truthful opening hooks and early retention.",
        )
        self.provider = provider or DeterministicCreativeQualityProvider()

    def perform_task(self, task: TaskRecord) -> OperationResult:
        """Return deterministic hook analysis from structured task input."""

        script = require_model(task.input_data, "video_script", VideoScript)
        analysis = self.provider.review_hook(script)
        return OperationResult.ok(
            "Hook Architect completed deterministic hook review.",
            data={"hook_analysis": analysis.model_dump(mode="json")},
        )
