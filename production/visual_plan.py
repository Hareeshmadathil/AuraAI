"""Visual request planning without external generation providers."""

from __future__ import annotations

from production.models import (
    AssetStatus,
    AssetType,
    Storyboard,
    VideoFormat,
    VisualAssetRequest,
    VisualGenerationPlan,
    VisualRequestKind,
    VideoStyle,
)


class VisualPlanBuilder:
    """Convert storyboard scenes into explicitly not-generated requests."""

    def build(
        self,
        storyboard: Storyboard,
        video_format: VideoFormat,
    ) -> VisualGenerationPlan:
        """Create one planned visual request per scene."""

        aspect_ratio = (
            "16:9"
            if video_format == VideoFormat.YOUTUBE_LONG_FORM
            else "9:16"
        )
        requests = [
            VisualAssetRequest(
                scene_id=scene.scene_id,
                asset_type=AssetType.VISUAL_PROMPT,
                request_kind=self._request_kind(scene.style, scene.sequence_number),
                style=scene.style,
                prompt=scene.visual_prompt,
                negative_prompt=scene.negative_prompt,
                aspect_ratio=aspect_ratio,
                target_duration_seconds=round(
                    scene.end_seconds - scene.start_seconds, 2
                ),
                continuity_reference=(
                    "Follow storyboard palette, object scale, and typography rules."
                ),
                rights_requirements=[
                    "Use only original, public-domain, or properly licensed assets.",
                    "Do not imitate living artists or protected characters.",
                ],
                status=AssetStatus.NOT_GENERATED,
                output_path=None,
                sample_data=storyboard.sample_data,
            )
            for scene in storyboard.scenes
        ]
        return VisualGenerationPlan(
            storyboard_id=storyboard.storyboard_id,
            requests=requests,
            estimated_asset_count=len(requests),
            consistency_rules=[
                *storyboard.style_continuity_notes,
                *storyboard.character_continuity_notes,
            ],
            fallback_asset_strategy=[
                "Use an original motion-graphic diagram when a scene asset is unavailable.",
                "Use a licensed stock-like placeholder only after rights verification.",
                "Never imply a placeholder is a generated or final production asset.",
            ],
            sample_data=storyboard.sample_data,
        )

    @staticmethod
    def _request_kind(
        style: VideoStyle,
        sequence_number: int,
    ) -> VisualRequestKind:
        """Choose a provider-neutral visual treatment for one scene."""

        if style in {VideoStyle.MOTION_GRAPHICS, VideoStyle.ANIMATION}:
            return VisualRequestKind.MOTION_GRAPHIC
        if style == VideoStyle.ANIME:
            return VisualRequestKind.IMAGE
        if style in {
            VideoStyle.LIVE_ACTION,
            VideoStyle.CINEMATIC_LIVE_ACTION,
            VideoStyle.DOCUMENTARY,
        }:
            return (
                VisualRequestKind.B_ROLL
                if sequence_number % 2
                else VisualRequestKind.STOCK_PLACEHOLDER
            )
        hybrid_kinds = (
            VisualRequestKind.MOTION_GRAPHIC,
            VisualRequestKind.B_ROLL,
            VisualRequestKind.IMAGE,
            VisualRequestKind.VIDEO_GENERATION,
        )
        return hybrid_kinds[(sequence_number - 1) % len(hybrid_kinds)]
