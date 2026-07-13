"""Deterministic Production Storyboard Artist."""

from agents.base_employee import BaseEmployee
from core import DepartmentName, OperationResult, TaskRecord
from production.models import ContentBrief, VideoScript
from production.storyboard_engine import StoryboardEngine
from production.task_inputs import require_model


class StoryboardArtist(BaseEmployee):
    """Create safe sequential storyboard scenes from a script."""

    def __init__(self, engine: StoryboardEngine | None = None) -> None:
        super().__init__(
            name="Frame",
            job_title="Storyboard Artist",
            department=DepartmentName.PRODUCTION,
            description="Creates timed provider-neutral visual and shot directions.",
        )
        self.engine = engine or StoryboardEngine()

    def perform_task(self, task: TaskRecord) -> OperationResult:
        script = require_model(task.input_data, "video_script", VideoScript)
        brief = require_model(task.input_data, "content_brief", ContentBrief)
        storyboard = self.engine.build(script, brief)
        return OperationResult.ok(
            "Storyboard Artist created the sequential storyboard.",
            data={"storyboard": storyboard.model_dump(mode="json")},
        )
