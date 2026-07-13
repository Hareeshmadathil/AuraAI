"""Cross-platform short-form derivative planning."""

from __future__ import annotations

from core import ContentPlatform
from production.models import ShortFormAsset, ShortFormPackage, Storyboard, VideoScript


class ShortFormEngine:
    """Adapt long-form ideas into standalone platform concepts."""

    _PLATFORMS = (
        ContentPlatform.YOUTUBE_SHORTS,
        ContentPlatform.INSTAGRAM,
        ContentPlatform.TIKTOK,
    )

    def build(self, script: VideoScript, storyboard: Storyboard) -> ShortFormPackage:
        """Create three distinct concepts per supported short-form platform."""

        scene_groups = self._scene_groups(storyboard)
        assets: list[ShortFormAsset] = []
        for platform in self._PLATFORMS:
            for index, scenes in enumerate(scene_groups, start=1):
                narration = self._narration(script, index)
                assets.append(
                    ShortFormAsset(
                        source_script_id=script.script_id,
                        platform=platform,
                        title=self._title(platform, script, index),
                        hook=self._hook(platform, script, index),
                        narration=narration,
                        selected_scene_ids=[scene.scene_id for scene in scenes],
                        target_duration_seconds=45.0 if index < 3 else 55.0,
                        caption=self._caption(platform, script, index),
                        hashtags=self._hashtags(platform, script.primary_keyword),
                        call_to_action=self._cta(platform),
                        loop_strategy=self._loop(platform, index),
                        sample_data=script.sample_data,
                    )
                )
        return ShortFormPackage(
            source_script_id=script.script_id,
            assets=assets,
        )

    @staticmethod
    def _scene_groups(storyboard: Storyboard) -> list[list]:
        scenes = storyboard.scenes
        indexes = ((0, 1), (2, 3), (4, 5))
        return [
            [scenes[index % len(scenes)] for index in pair]
            for pair in indexes
        ]

    @staticmethod
    def _narration(script: VideoScript, index: int) -> str:
        section = script.sections[min(index, len(script.sections) - 1)]
        return (
            f"{section.title}. {section.narration} "
            "This is a planning draft: verify factual claims before publishing."
        )

    @staticmethod
    def _title(platform: ContentPlatform, script: VideoScript, index: int) -> str:
        labels = {1: "Find the bottleneck", 2: "Build the review gate", 3: "Measure the change"}
        return f"{labels[index]} | {script.primary_keyword}"

    @staticmethod
    def _hook(platform: ContentPlatform, script: VideoScript, index: int) -> str:
        prefix = {
            ContentPlatform.YOUTUBE_SHORTS: "One practical idea in under a minute:",
            ContentPlatform.INSTAGRAM: "Save this workflow check:",
            ContentPlatform.TIKTOK: "Before you automate another task, ask this:",
        }[platform]
        angles = (
            "What repeats often enough to measure?",
            "Who reviews the output before it matters?",
            "Which local metric proves the change helped?",
        )
        return f"{prefix} {angles[index - 1]}"

    @staticmethod
    def _caption(platform: ContentPlatform, script: VideoScript, index: int) -> str:
        platform_note = {
            ContentPlatform.YOUTUBE_SHORTS: "Watch the full guide for context.",
            ContentPlatform.INSTAGRAM: "Save the framework and share it with the process owner.",
            ContentPlatform.TIKTOK: "Comment with the workflow you would audit first.",
        }[platform]
        return (
            f"Part {index}: a responsible {script.primary_keyword} workflow. "
            f"No outcome is guaranteed. {platform_note}"
        )

    @staticmethod
    def _hashtags(platform: ContentPlatform, keyword: str) -> list[str]:
        primary = "#" + "".join(character for character in keyword.title() if character.isalnum())
        specific = {
            ContentPlatform.YOUTUBE_SHORTS: "#YouTubeShorts",
            ContentPlatform.INSTAGRAM: "#ReelsEducation",
            ContentPlatform.TIKTOK: "#LearnOnTikTok",
        }[platform]
        return [primary, specific, "#SmallBusiness", "#WorkflowDesign"]

    @staticmethod
    def _cta(platform: ContentPlatform) -> str:
        return {
            ContentPlatform.YOUTUBE_SHORTS: "Continue with the full educational guide.",
            ContentPlatform.INSTAGRAM: "Save this and review one workflow today.",
            ContentPlatform.TIKTOK: "Follow for the next responsible workflow step.",
        }[platform]

    @staticmethod
    def _loop(platform: ContentPlatform, index: int) -> str:
        return (
            f"End by returning to question {index}; the opening frame can follow naturally. "
            f"Adapt pacing for {platform.value} rather than duplicating an edit."
        )
