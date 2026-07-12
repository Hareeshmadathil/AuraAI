"""TikTok platform management planning for AuraAI Creator OS."""

from __future__ import annotations

from agents.specialists.seo_specialist import SEOPlan
from agents.specialists.platform_manager_base import (
    PlatformContentFormat,
    PlatformGrowthPlan,
    PlatformManagerBase,
    PlatformPublishingPlan,
)
from core import ContentPlatform


class TikTokManager(PlatformManagerBase):
    """Manager for deterministic TikTok vertical-video planning."""

    def __init__(self) -> None:
        super().__init__(name="Pulse", job_title="TikTok Manager")

    @property
    def supported_platforms(self) -> frozenset[ContentPlatform]:
        """Return TikTok as the sole platform scope."""

        return frozenset({ContentPlatform.TIKTOK})

    def create_platform_plan(
        self,
        *,
        brand_name: str,
        positioning: str,
        target_audience: str,
        content_pillars: list[str],
        campaign_goal: str,
        publishing_frequency: str,
        seo_plan: SEOPlan,
    ) -> PlatformPublishingPlan:
        """Create discovery and eligibility-aware vertical formats."""

        self._validate_seo_platform(seo_plan)
        return PlatformPublishingPlan(
            brand_name=brand_name,
            positioning=positioning,
            target_audience=target_audience,
            content_pillars=content_pillars,
            campaign_goal=campaign_goal,
            supported_platforms=[ContentPlatform.TIKTOK],
            platform_roles={
                ContentPlatform.TIKTOK: (
                    "Vertical-video discovery, topic testing, and direct "
                    "audience feedback."
                )
            },
            content_formats=[
                PlatformContentFormat(
                    platform=ContentPlatform.TIKTOK,
                    name="Short discovery video",
                    role="Test one hook or useful idea with a fast payoff.",
                    production_guidance=[
                        "State the topic immediately.",
                        "Use fast pacing only when clarity is preserved.",
                    ],
                ),
                PlatformContentFormat(
                    platform=ContentPlatform.TIKTOK,
                    name="Extended eligibility-aware video",
                    role=(
                        "Provide deeper original value when longer videos "
                        "are relevant to current monetization requirements."
                    ),
                    production_guidance=[
                        "Do not extend runtime solely to pursue eligibility.",
                        "Verify current program rules before execution.",
                    ],
                ),
            ],
            publishing_cadence=publishing_frequency,
            profile_guidance=[
                f"Identify the account as {brand_name}.",
                "State the audience promise clearly and avoid guarantees.",
            ],
            caption_guidance=[
                seo_plan.description_guidance,
                "Keep the caption accurate to the spoken video content.",
            ],
            hashtag_guidance=seo_plan.hashtag_guidance,
            hook_and_pacing_guidance=[
                "Open with the audience problem, result, or useful tension.",
                "Deliver evidence or explanation immediately after the hook.",
                "Use visual changes to support meaning, not distraction.",
            ],
            growth_plan=PlatformGrowthPlan(
                audience_retention_priorities=[
                    "Resolve the opening promise within the video.",
                    "Remove pauses and repetition that do not add clarity.",
                ],
                engagement_priorities=[
                    "Use substantive comments as future topic evidence.",
                    "Test hook variants without changing factual claims.",
                ],
                monetization_paths=[
                    "Platform programs only after verifying current regional "
                    "and content eligibility; earnings are not guaranteed.",
                    "Disclosed sponsorships or affiliates when relevant.",
                    "Audience-aligned owned offerings after demand validation.",
                ],
            ),
            seo_plan_id=seo_plan.seo_plan_id,
        )
