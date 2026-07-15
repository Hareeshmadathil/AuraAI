"""Private render manifest creation."""

from pathlib import Path

from private_video_production.models import (
    RenderManifest,
    RenderSpecification,
    ScenePlan,
    VoiceSynthesisResult,
)


def build_render_manifest(
    *,
    mission_id,
    specification: RenderSpecification,
    scenes: list[ScenePlan],
    voice_result: VoiceSynthesisResult | None,
    missing_asset_ids: list[str],
) -> RenderManifest:
    """Build a never-published render plan even when execution is blocked."""

    duration = max(scene.expected_end_seconds for scene in scenes)
    return RenderManifest(
        mission_id=mission_id,
        specification=specification,
        scene_relative_paths=[Path(f"scenes/{scene.scene_id}.mp4") for scene in scenes],
        narration_relative_path=(
            voice_result.output_relative_path if voice_result and voice_result.success else None
        ),
        subtitle_relative_path=Path("subtitles/mission-zero.srt"),
        expected_duration_seconds=duration,
        missing_asset_ids=missing_asset_ids,
        placeholder_count=sum(scene.founder_capture_required for scene in scenes),
        publishing_allowed=False,
    )
