"""
Specialist employees for AuraAI Creator OS.
"""

from agents.specialists.trend_hunter import (
    TrendCandidate,
    TrendHunter,
    TrendOpportunity,
)
from agents.specialists.seo_specialist import (
    SEOKeywordCandidate,
    SEOPlan,
    SEORecommendation,
    SEOSpecialist,
)
from agents.specialists.instagram_manager import InstagramManager
from agents.specialists.tiktok_manager import TikTokManager
from agents.specialists.platform_manager_base import (
    PlatformContentFormat,
    PlatformGrowthPlan,
    PlatformPublishingPlan,
)
from agents.specialists.youtube_manager import YouTubeManager

__all__ = [
    "TrendCandidate",
    "TrendHunter",
    "TrendOpportunity",
    "SEOKeywordCandidate",
    "SEOPlan",
    "SEORecommendation",
    "SEOSpecialist",
    "InstagramManager",
    "PlatformContentFormat",
    "PlatformGrowthPlan",
    "PlatformPublishingPlan",
    "TikTokManager",
    "YouTubeManager",
]
