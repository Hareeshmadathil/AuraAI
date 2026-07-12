"""Instagram platform management planning for AuraAI Creator OS."""

from __future__ import annotations

from agents.specialists.seo_specialist import SEOPlan
from agents.specialists.youtube_manager import (
    PlatformContentFormat,
    PlatformGrowthPlan,
    PlatformManagerBase,
    PlatformPublishingPlan,
)
from core import ContentPlatform


class InstagramManager(PlatformManagerBase):
    """Manager for Reels-first Instagram campaign planning."""

    def __init__(self) -> None:
        super().__init__(name="Canvas", job_title="Instagram Manager")

    @property
    def supported_platforms(self) -> frozenset[ContentPlatform]:
        """Return Instagram as the sole platform scope."""

        return frozenset({ContentPlatform.INSTAGRAM})

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
        """Create a Reels-first plan with carousel and Story support."""

        self._validate_seo_platform(seo_plan)
        return PlatformPublishingPlan(
            brand_name=brand_name,
            positioning=positioning,
            target_audience=target_audience,
            content_pillars=content_pillars,
            campaign_goal=campaign_goal,
            supported_platforms=[ContentPlatform.INSTAGRAM],
            platform_roles={
                ContentPlatform.INSTAGRAM: (
                    "Reels-first discovery with carousel education and "
                    "Story-based community support."
                )
            },
            content_formats=[
                PlatformContentFormat(
                    platform=ContentPlatform.INSTAGRAM,
                    name="Reel",
                    role="Primary discovery and concise education format.",
                    production_guidance=[
                        "Lead with a clear visual and spoken hook.",
                        "Use readable on-screen context without clutter.",
                    ],
                ),
                PlatformContentFormat(
                    platform=ContentPlatform.INSTAGRAM,
                    name="Carousel",
                    role="Support saves with structured reference content.",
                    production_guidance=[
                        "Give each slide one clear job.",
                        "Conclude with a practical summary or next step.",
                    ],
                ),
                PlatformContentFormat(
                    platform=ContentPlatform.INSTAGRAM,
                    name="Story",
                    role="Support feedback, context, and community contact.",
                    production_guidance=[
                        "Use questions and polls only when actionable.",
                        "Keep updates consistent with the campaign goal.",
                    ],
                ),
            ],
            publishing_cadence=publishing_frequency,
            profile_guidance=[
                f"Name the brand clearly as {brand_name}.",
                "Use the bio to state audience, value, and positioning.",
                "Avoid unverifiable authority or outcome claims.",
            ],
            caption_guidance=[
                seo_plan.description_guidance,
                "Lead with useful context and end with one relevant prompt.",
            ],
            hashtag_guidance=seo_plan.hashtag_guidance,
            growth_plan=PlatformGrowthPlan(
                audience_retention_priorities=[
                    "Make the Reel understandable without prior context.",
                    "Match on-screen pacing to information density.",
                ],
                engagement_priorities=[
                    "Prioritize meaningful saves, shares, and questions.",
                    "Use Story feedback to improve future Reels.",
                ],
                monetization_paths=[
                    "Relevant sponsorships with clear disclosure and no "
                    "earnings guarantee.",
                    "Affiliate recommendations only when audience-aligned.",
                    "Owned offerings after trust and demand are validated.",
                ],
            ),
            seo_plan_id=seo_plan.seo_plan_id,
        )
