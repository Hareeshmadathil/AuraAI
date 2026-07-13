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
from agents.specialists.quality_controller import QualityController
from agents.specialists.script_writer import ScriptWriter
from agents.specialists.shorts_editor import ShortsEditor
from agents.specialists.storyboard_artist import StoryboardArtist
from agents.specialists.thumbnail_designer import ThumbnailDesigner
from agents.specialists.video_editor import VideoEditor
from agents.specialists.voice_artist import VoiceArtist

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
    "QualityController",
    "ScriptWriter",
    "ShortsEditor",
    "StoryboardArtist",
    "ThumbnailDesigner",
    "VideoEditor",
    "VoiceArtist",
]
