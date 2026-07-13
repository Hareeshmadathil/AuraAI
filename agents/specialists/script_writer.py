"""Deterministic Production Script Writer."""

from agents.base_employee import BaseEmployee
from core import DepartmentName, OperationResult, TaskRecord
from production.models import ContentBrief
from production.script_engine import ScriptEngine
from production.task_inputs import require_model


class ScriptWriter(BaseEmployee):
    """Write meaningful scripts from supplied evidence without an LLM."""

    def __init__(self, engine: ScriptEngine | None = None) -> None:
        super().__init__(
            name="Quill",
            job_title="Script Writer",
            department=DepartmentName.PRODUCTION,
            description="Creates deterministic, factuality-aware educational scripts.",
        )
        self.engine = engine or ScriptEngine()

    def perform_task(self, task: TaskRecord) -> OperationResult:
        brief = require_model(task.input_data, "content_brief", ContentBrief)
        script = self.engine.build(brief)
        return OperationResult.ok(
            "Script Writer created the deterministic video script.",
            data={"video_script": script.model_dump(mode="json")},
        )
