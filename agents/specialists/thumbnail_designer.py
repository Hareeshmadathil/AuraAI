"""Deterministic Production Thumbnail Designer."""

from agents.base_employee import BaseEmployee
from core import DepartmentName, OperationResult, TaskRecord
from production.models import ContentBrief, VideoScript
from production.task_inputs import require_model
from production.thumbnail_plan import ThumbnailPlanBuilder


class ThumbnailDesigner(BaseEmployee):
    """Create truthful concepts without generating images."""

    def __init__(self, builder: ThumbnailPlanBuilder | None = None) -> None:
        super().__init__(
            name="Pixel",
            job_title="Thumbnail Designer",
            department=DepartmentName.PRODUCTION,
            description="Creates mobile-readable provider-neutral thumbnail concepts.",
        )
        self.builder = builder or ThumbnailPlanBuilder()

    def perform_task(self, task: TaskRecord) -> OperationResult:
        script = require_model(task.input_data, "video_script", VideoScript)
        brief = require_model(task.input_data, "content_brief", ContentBrief)
        plan = self.builder.build(script, brief)
        return OperationResult.ok(
            "Thumbnail Designer created three planned thumbnail concepts.",
            data={"thumbnail_plan": plan.model_dump(mode="json")},
        )
