"""Deterministic marketing strategy construction for AuraAI."""

from __future__ import annotations

from collections.abc import Sequence

from core import ContentPlatform, MissionRecord, TaskPriority
from marketing.marketing_models import (
    MarketingObjective,
    PlatformAssignment,
)


def build_marketing_objectives(
    mission: MissionRecord,
) -> list[MarketingObjective]:
    """Translate mission objectives into campaign objectives."""

    return [
        MarketingObjective(
            description=objective.description,
            success_metric=objective.success_metric,
            target_value=objective.target_value or "Mission target met",
            priority=mission.priority,
        )
        for objective in mission.objectives
    ]


def build_platform_assignments() -> list[PlatformAssignment]:
    """Define distinct roles for AuraAI's supported social platforms."""

    return [
        PlatformAssignment(
            platform=ContentPlatform.YOUTUBE,
            platform_role=(
                "Act as the authority and discovery hub for durable, "
                "searchable long-form content."
            ),
            content_formats=["Long-form videos", "Series playlists"],
            campaign_goal=(
                "Build trust, watch time, and a reusable content library."
            ),
            expected_outputs=[
                "Long-form episode briefs",
                "Search-focused titles and descriptions",
            ],
            priority=TaskPriority.HIGH,
        ),
        PlatformAssignment(
            platform=ContentPlatform.YOUTUBE_SHORTS,
            platform_role=(
                "Turn core ideas into concise discovery content that "
                "directs interested viewers toward deeper resources."
            ),
            content_formats=["Vertical clips", "Standalone short tips"],
            campaign_goal="Expand qualified reach through short video.",
            expected_outputs=[
                "Short-video briefs",
                "Hooks and calls to action",
            ],
            priority=TaskPriority.HIGH,
        ),
        PlatformAssignment(
            platform=ContentPlatform.INSTAGRAM,
            platform_role=(
                "Express the brand visually and nurture an engaged "
                "community through educational, shareable content."
            ),
            content_formats=["Reels", "Carousels", "Stories"],
            campaign_goal=(
                "Increase saves, shares, and recurring audience contact."
            ),
            expected_outputs=[
                "Reel and carousel briefs",
                "Community engagement prompts",
            ],
        ),
        PlatformAssignment(
            platform=ContentPlatform.TIKTOK,
            platform_role=(
                "Test timely hooks and accessible explanations for rapid "
                "audience feedback and discovery."
            ),
            content_formats=["Native vertical videos", "Trend responses"],
            campaign_goal=(
                "Validate topics and creative angles with fast feedback."
            ),
            expected_outputs=[
                "Native video briefs",
                "Hook variants and learning notes",
            ],
        ),
    ]


def expected_marketing_outputs(
    assignments: Sequence[PlatformAssignment],
) -> list[str]:
    """Create the consolidated output list for a marketing plan."""

    outputs = [
        "Final approval package for brand and campaign execution",
        "Cross-platform campaign calendar",
    ]

    for assignment in assignments:
        outputs.extend(assignment.expected_outputs)

    return outputs
