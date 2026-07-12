"""YouTube platform management planning for AuraAI Creator OS."""

from __future__ import annotations

from agents.specialists.platform_manager_base import (
    PlatformContentFormat,
    PlatformGrowthPlan,
    PlatformManagerBase,
    PlatformPublishingPlan,
)
from agents.specialists.seo_specialist import SEOPlan
from core import ContentPlatform


class YouTubeManager(PlatformManagerBase):
    """Manager for YouTube long-form and YouTube Shorts planning."""

    def __init__(self) -> None:
        super().__init__(name="Frame", job_title="YouTube Manager")

    @property
    def supported_platforms(self) -> frozenset[ContentPlatform]:
        """Return the manager's YouTube platform scope."""

        return frozenset(
            {
                ContentPlatform.YOUTUBE,
                ContentPlatform.YOUTUBE_SHORTS,
            }
        )

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
        """Create coordinated long-form and Shorts channel roles."""

        self._validate_seo_platform(seo_plan)
        return PlatformPublishingPlan(
            brand_name=brand_name,
            positioning=positioning,
            target_audience=target_audience,
            content_pillars=content_pillars,
            campaign_goal=campaign_goal,
            supported_platforms=list(self.supported_platforms),
            platform_roles={
                ContentPlatform.YOUTUBE: (
                    "Authority, search discovery, and durable education."
                ),
                ContentPlatform.YOUTUBE_SHORTS: (
                    "Concise discovery that introduces core ideas and "
                    "guides interested viewers to deeper content."
                ),
            },
            content_formats=[
                PlatformContentFormat(
                    platform=ContentPlatform.YOUTUBE,
                    name="Long-form educational video",
                    role="Deliver complete, searchable topic coverage.",
                    production_guidance=[
                        "Open with the audience problem and outcome.",
                        "Use clear sections and evidence-based examples.",
                    ],
                ),
                PlatformContentFormat(
                    platform=ContentPlatform.YOUTUBE_SHORTS,
                    name="Vertical discovery Short",
                    role="Deliver one useful idea with a complete payoff.",
                    production_guidance=[
                        "Lead with the value in the opening seconds.",
                        "Avoid withholding the promised answer.",
                    ],
                ),
            ],
            publishing_cadence=publishing_frequency,
            title_guidance=[
                seo_plan.title_guidance,
                "Keep the title specific and consistent with the video.",
            ],
            thumbnail_guidance=[
                "Communicate one clear idea with readable visual hierarchy.",
                "Do not imply outcomes the video cannot support.",
            ],
            growth_plan=PlatformGrowthPlan(
                audience_retention_priorities=[
                    "Confirm the promised value early.",
                    "Remove repetition and maintain logical progression.",
                    "End each section with a reason to continue.",
                ],
                engagement_priorities=[
                    "Invite relevant questions and future-topic requests.",
                    "Use Shorts feedback to refine long-form topics.",
                ],
                monetization_paths=[
                    "Platform advertising after applicable eligibility, "
                    "with no revenue guarantee.",
                    "Relevant sponsorships or affiliates with disclosure, "
                    "subject to audience trust and partner approval.",
                    "Owned products or services when genuinely relevant.",
                ],
            ),
            seo_plan_id=seo_plan.seo_plan_id,
        )
