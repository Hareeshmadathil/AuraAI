"""Motion Designer employee."""

from agents.base_employee import BaseEmployee
from core import DepartmentName, OperationResult, TaskRecord
from creative_quality.motion_engine import MotionEngine
from creative_quality.task_inputs import require_model
from production.models import Storyboard


class MotionDesigner(BaseEmployee):
    """Create accessible provider-neutral motion direction."""

    def __init__(self, engine: MotionEngine | None = None) -> None:
        super().__init__(
            name="Flux",
            job_title="Motion Designer",
            department=DepartmentName.CREATIVE_QUALITY,
            description="Plans restrained motion, emphasis, and scene rhythm.",
        )
        self.engine = engine or MotionEngine()

    def perform_task(self, task: TaskRecord) -> OperationResult:
        """Return one deterministic cue plan for the supplied storyboard."""

        storyboard = require_model(task.input_data, "storyboard", Storyboard)
        plan = self.engine.analyze(storyboard)
        return OperationResult.ok(
            "Motion Designer created the deterministic motion plan.",
            data={"motion_plan": plan.model_dump(mode="json")},
        )
