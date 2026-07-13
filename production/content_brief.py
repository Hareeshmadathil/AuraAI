"""Deterministic content-brief construction and style selection."""

from __future__ import annotations

import math

from core import ContentPlatform, ValidationError
from production.models import (
    ContentBrief,
    ProductionInput,
    VideoFormat,
    VideoStyle,
)


class ContentBriefBuilder:
    """Build a factual, provider-neutral brief from explicit input."""

    _FORMAT_BY_PLATFORM = {
        ContentPlatform.YOUTUBE: VideoFormat.YOUTUBE_LONG_FORM,
        ContentPlatform.YOUTUBE_SHORTS: VideoFormat.YOUTUBE_SHORT,
        ContentPlatform.INSTAGRAM: VideoFormat.INSTAGRAM_REEL,
        ContentPlatform.TIKTOK: VideoFormat.TIKTOK_VIDEO,
    }

    def build(self, production_input: ProductionInput) -> ContentBrief:
        """Validate input and create a deterministic content brief."""

        value = ProductionInput.model_validate(production_input)
        style, reason = self._select_style(value)
        scene_length = 35 if value.target_duration_seconds >= 180 else 15
        scene_count = max(
            1,
            math.ceil(value.target_duration_seconds / scene_length),
        )
        return ContentBrief(
            production_input=value,
            selected_style=style,
            format=self._FORMAT_BY_PLATFORM[value.primary_platform],
            creative_direction=(
                f"Use a {style.value.replace('_', ' ')} treatment. {reason} "
                "Every visual remains a planned direction until a licensed "
                "or original asset is supplied by a future provider."
            ),
            core_message=(
                f"Help {value.target_audience} understand {value.topic} and "
                f"make progress on: {value.audience_problem}"
            ),
            learning_outcomes=[
                f"Explain the practical meaning of {value.topic}.",
                "Identify a safe first action and its limitations.",
                "Distinguish evidence-backed guidance from assumptions.",
            ],
            hook_strategy=(
                f"Open with the audience problem, promise {value.audience_promise}, "
                "and preview a concrete result without exaggeration."
            ),
            narrative_structure=[
                "Problem-led cold open",
                "Audience context and stakes",
                "Step-by-step educational framework",
                "Practical example and limitations",
                "Summary and next action",
            ],
            evidence_requirements=[
                "Use only supplied source notes for factual claims.",
                "Mark material claims requiring independent verification.",
                "Separate illustrative examples from measured outcomes.",
                "Review time-sensitive facts before publication.",
            ],
            prohibited_claims=[
                "Guaranteed income, views, growth, or monetization",
                "Unsupported medical, legal, or financial advice",
                "Fabricated statistics, testimonials, or provider capabilities",
                "Ownership of unlicensed brands or copyrighted assets",
            ],
            monetization_alignment=(
                f"Align the educational value with {value.campaign_goal}. Future "
                "sponsorship, affiliate, product, or service paths may be reviewed, "
                "but no earnings or eligibility outcome is promised."
            ),
            estimated_scene_count=scene_count,
        )

    @staticmethod
    def _select_style(value: ProductionInput) -> tuple[VideoStyle, str]:
        """Select a style from topic signals while honoring explicit input."""

        if value.preferred_style is not None:
            return (
                value.preferred_style,
                "The explicitly requested supported style was preserved.",
            )
        text = " ".join(
            [value.topic, *value.content_pillars, value.campaign_goal]
        ).casefold()
        if any(term in text for term in ("fantasy", "storytelling", "series")):
            return VideoStyle.ANIMATION, (
                "Narrative subject signals favor an original animated treatment."
            )
        if any(
            term in text
            for term in ("business", "technology", "finance", "education", "ai")
        ):
            return VideoStyle.HYBRID, (
                "The educational business topic benefits from documentary context "
                "combined with clear motion-graphic explanations."
            )
        if not value.topic.strip():
            raise ValidationError("Production topic cannot be empty.")
        return VideoStyle.MOTION_GRAPHICS, (
            "A broad explanatory topic is clearest with reusable motion graphics."
        )
