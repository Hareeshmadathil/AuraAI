"""Provider-neutral Production Voice Artist."""

from agents.base_employee import BaseEmployee
from core import DepartmentName, OperationResult, TaskRecord
from production.models import Storyboard, VideoScript
from production.task_inputs import require_model, require_text
from production.voice_plan import VoicePlanBuilder


class VoiceArtist(BaseEmployee):
    """Plan voice timing and performance without synthesizing audio."""

    def __init__(self, builder: VoicePlanBuilder | None = None) -> None:
        super().__init__(
            name="Vox",
            job_title="Voice Artist",
            department=DepartmentName.PRODUCTION,
            description="Creates provider-neutral scene-linked voiceover plans.",
        )
        self.builder = builder or VoicePlanBuilder()

    def perform_task(self, task: TaskRecord) -> OperationResult:
        script = require_model(task.input_data, "video_script", VideoScript)
        storyboard = require_model(task.input_data, "storyboard", Storyboard)
        plan = self.builder.build(
            script,
            storyboard,
            language=require_text(task.input_data, "language"),
            tone=require_text(task.input_data, "tone"),
        )
        return OperationResult.ok(
            "Voice Artist created a voiceover plan; no audio was synthesized.",
            data={"voiceover_plan": plan.model_dump(mode="json")},
        )
