"""Planned video-assembly manifest construction."""

from __future__ import annotations

import re

from production.models import (
    AssemblyTrackItem,
    AssetStatus,
    RenderStatus,
    Storyboard,
    SubtitlePackage,
    ThumbnailPlan,
    TrackType,
    VideoAssemblyManifest,
    VideoFormat,
    VideoScript,
    VisualGenerationPlan,
    VoiceoverPlan,
)


class AssemblyManifestBuilder:
    """Connect production plans into a safe, non-rendered manifest."""

    _DIMENSIONS = {
        VideoFormat.YOUTUBE_LONG_FORM: (1920, 1080),
        VideoFormat.YOUTUBE_SHORT: (1080, 1920),
        VideoFormat.INSTAGRAM_REEL: (1080, 1920),
        VideoFormat.TIKTOK_VIDEO: (1080, 1920),
    }

    def build(
        self,
        *,
        script: VideoScript,
        storyboard: Storyboard,
        voiceover_plan: VoiceoverPlan,
        visual_plan: VisualGenerationPlan,
        subtitle_package: SubtitlePackage,
        thumbnail_plan: ThumbnailPlan,
        video_format: VideoFormat,
    ) -> VideoAssemblyManifest:
        """Create logical tracks and explicitly mark rendering as pending."""

        width, height = self._DIMENSIONS[video_format]
        items: list[AssemblyTrackItem] = []
        for scene, request, voice in zip(
            storyboard.scenes,
            visual_plan.requests,
            voiceover_plan.segments,
            strict=True,
        ):
            items.extend(
                [
                    AssemblyTrackItem(
                        track_type=TrackType.VIDEO,
                        scene_id=scene.scene_id,
                        start_seconds=scene.start_seconds,
                        end_seconds=scene.end_seconds,
                        source_reference=f"visual-request:{request.request_id}",
                        instructions="Replace planned request with a rights-cleared visual before rendering.",
                        required=True,
                        status=AssetStatus.PLANNED,
                    ),
                    AssemblyTrackItem(
                        track_type=TrackType.VOICE,
                        scene_id=scene.scene_id,
                        start_seconds=scene.start_seconds,
                        end_seconds=scene.end_seconds,
                        source_reference=f"voice-segment:{voice.segment_id}",
                        instructions="Record or synthesize only after provider and script approval.",
                        required=True,
                        status=AssetStatus.PLANNED,
                    ),
                ]
            )
        duration = storyboard.total_duration_seconds
        items.extend(
            [
                AssemblyTrackItem(
                    track_type=TrackType.MUSIC,
                    start_seconds=0,
                    end_seconds=duration,
                    source_reference="music:licensed-placeholder",
                    instructions="Select original or properly licensed music; duck beneath narration.",
                    required=False,
                ),
                AssemblyTrackItem(
                    track_type=TrackType.SUBTITLE,
                    start_seconds=0,
                    end_seconds=duration,
                    source_reference=f"subtitle-package:{subtitle_package.package_id}",
                    instructions="Import validated captions and verify final timing.",
                    required=True,
                ),
                AssemblyTrackItem(
                    track_type=TrackType.MOTION_GRAPHICS,
                    start_seconds=0,
                    end_seconds=duration,
                    source_reference="graphics:planned-overlays",
                    instructions="Add only factual, readable labels described by the storyboard.",
                    required=False,
                ),
                AssemblyTrackItem(
                    track_type=TrackType.TRANSITION,
                    start_seconds=0,
                    end_seconds=duration,
                    source_reference="transitions:storyboard-directions",
                    instructions="Use restrained cuts and dissolves from scene directions.",
                    required=False,
                ),
            ]
        )
        return VideoAssemblyManifest(
            script_id=script.script_id,
            storyboard_id=storyboard.storyboard_id,
            voiceover_plan_id=voiceover_plan.plan_id,
            visual_plan_id=visual_plan.plan_id,
            format=video_format,
            width=width,
            height=height,
            frame_rate=30,
            audio_sample_rate=48_000,
            duration_seconds=duration,
            track_items=items,
            subtitle_package_id=subtitle_package.package_id,
            thumbnail_plan_id=thumbnail_plan.plan_id,
            output_filename=f"{self.sanitize_filename(script.title)}.mp4",
            output_directory="outputs/production",
            render_status=RenderStatus.NOT_RENDERED,
            sample_data=script.sample_data,
        )

    @staticmethod
    def sanitize_filename(value: str) -> str:
        """Return a portable filename stem with no path components."""

        clean = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-_.")
        return (clean or "auraai-production")[:120]
