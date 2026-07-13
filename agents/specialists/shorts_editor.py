"""Deterministic Production Shorts Editor."""

from agents.base_employee import BaseEmployee
from core import DepartmentName, OperationResult, TaskRecord
from production.models import Storyboard, VideoScript
from production.short_form_engine import ShortFormEngine
from production.task_inputs import require_model


class ShortsEditor(BaseEmployee):
    """Plan platform-adapted derivatives without rendering or publishing."""

    def __init__(self, engine: ShortFormEngine | None = None) -> None:
        super().__init__(
            name="Spark",
            job_title="Shorts Editor",
            department=DepartmentName.PRODUCTION,
            description="Creates standalone Shorts, Reels, and TikTok concepts.",
        )
        self.engine = engine or ShortFormEngine()

    def perform_task(self, task: TaskRecord) -> OperationResult:
        script = require_model(task.input_data, "video_script", VideoScript)
        storyboard = require_model(task.input_data, "storyboard", Storyboard)
        package = self.engine.build(script, storyboard)
        return OperationResult.ok(
            "Shorts Editor created platform-adapted short-form plans.",
            data={"short_form_package": package.model_dump(mode="json")},
        )
