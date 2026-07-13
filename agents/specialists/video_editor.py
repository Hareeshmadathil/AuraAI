"""Deterministic Production Video Editor."""

from agents.base_employee import BaseEmployee
from core import DepartmentName, OperationResult, TaskRecord, ValidationError
from production.assembly_manifest import AssemblyManifestBuilder
from production.models import (
    Storyboard,
    SubtitlePackage,
    ThumbnailPlan,
    VideoFormat,
    VideoScript,
    VisualGenerationPlan,
    VoiceoverPlan,
)
from production.task_inputs import require_model


class VideoEditor(BaseEmployee):
    """Create a planned assembly manifest without invoking FFmpeg."""

    def __init__(self, builder: AssemblyManifestBuilder | None = None) -> None:
        super().__init__(
            name="Cut",
            job_title="Video Editor",
            department=DepartmentName.PRODUCTION,
            description="Connects planned production assets in a non-rendered manifest.",
        )
        self.builder = builder or AssemblyManifestBuilder()

    def perform_task(self, task: TaskRecord) -> OperationResult:
        manifest = self.builder.build(
            script=require_model(task.input_data, "video_script", VideoScript),
            storyboard=require_model(task.input_data, "storyboard", Storyboard),
            voiceover_plan=require_model(task.input_data, "voiceover_plan", VoiceoverPlan),
            visual_plan=require_model(task.input_data, "visual_plan", VisualGenerationPlan),
            subtitle_package=require_model(task.input_data, "subtitle_package", SubtitlePackage),
            thumbnail_plan=require_model(task.input_data, "thumbnail_plan", ThumbnailPlan),
            video_format=self._video_format(task.input_data.get("video_format")),
        )
        return OperationResult.ok(
            "Video Editor created the planned, non-rendered assembly manifest.",
            data={"assembly_manifest": manifest.model_dump(mode="json")},
        )

    @staticmethod
    def _video_format(value: object) -> VideoFormat:
        try:
            return value if isinstance(value, VideoFormat) else VideoFormat(value)
        except (TypeError, ValueError) as error:
            raise ValidationError("A supported video_format is required.") from error
