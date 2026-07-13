"""Neutral factory for AuraAI's currently implemented company roster."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from agents.base_employee import BaseEmployee
from agents.directors import (
    CreativeDirector,
    DistributionDirector,
    ProductionDirector,
    ResearchDirector,
    SEODirector,
    StrategyDirector,
)
from agents.executive import AuraCEO, AuraCOO
from agents.specialists import (
    AudienceAnalyst,
    CompetitorAnalyst,
    InstagramManager,
    QualityController,
    RetentionEngineer,
    SEOSpecialist,
    ScriptWriter,
    ShortsEditor,
    StoryboardArtist,
    TikTokManager,
    ThumbnailAnalyst,
    ThumbnailDesigner,
    TrendHunter,
    TrendAnalyst,
    VideoEditor,
    VoiceArtist,
    YouTubeManager,
    FactualityReviewer,
    HookArchitect,
    MotionDesigner,
    RetentionAuditor,
    StoryDirector,
    SubtitleDesigner,
    ThumbnailPsychologist,
    AnalyticsEngineer,
    LearningEngineer,
    MetadataSpecialist,
    PerformanceAnalyst,
    SEOPublisher,
    ShortFormDistributionSpecialist,
    YouTubeDistributionSpecialist,
)
from analytics.providers import DeterministicAnalyticsProvider
from intelligence.providers import DeterministicIntelligenceProvider
from marketing import MarketingDirector


@dataclass(frozen=True, slots=True)
class CompanyRoster:
    """Immutable grouping of implemented AuraAI employee instances."""

    executives: tuple[BaseEmployee, ...]
    directors: tuple[BaseEmployee, ...]
    specialists: tuple[BaseEmployee, ...]

    def __post_init__(self) -> None:
        """Reject accidental duplicate employee identifiers."""

        agent_ids = [employee.agent_id for employee in self.employees]
        if len(agent_ids) != len(set(agent_ids)):
            raise ValueError("Company roster contains duplicate agent IDs.")

    @property
    def employees(self) -> tuple[BaseEmployee, ...]:
        """Return every employee in organizational order."""

        return self.executives + self.directors + self.specialists


def create_company_roster() -> CompanyRoster:
    """Construct the current AuraAI company from existing classes."""

    intelligence_provider = DeterministicIntelligenceProvider()
    analytics_provider = DeterministicAnalyticsProvider()
    roster = CompanyRoster(
        executives=(AuraCEO(), AuraCOO()),
        directors=(
            StrategyDirector(),
            ResearchDirector(),
            MarketingDirector(),
            SEODirector(intelligence_provider),
            ProductionDirector(),
            CreativeDirector(),
            DistributionDirector(),
        ),
        specialists=(
            TrendHunter(),
            SEOSpecialist(),
            YouTubeManager(),
            InstagramManager(),
            TikTokManager(),
            TrendAnalyst(intelligence_provider),
            CompetitorAnalyst(intelligence_provider),
            AudienceAnalyst(intelligence_provider),
            RetentionEngineer(intelligence_provider),
            ThumbnailAnalyst(intelligence_provider),
            ScriptWriter(),
            StoryboardArtist(),
            VoiceArtist(),
            ThumbnailDesigner(),
            ShortsEditor(),
            VideoEditor(),
            QualityController(),
            HookArchitect(),
            StoryDirector(),
            MotionDesigner(),
            SubtitleDesigner(),
            ThumbnailPsychologist(),
            RetentionAuditor(),
            FactualityReviewer(),
            YouTubeDistributionSpecialist(),
            ShortFormDistributionSpecialist(),
            SEOPublisher(),
            MetadataSpecialist(),
            AnalyticsEngineer(analytics_provider),
            PerformanceAnalyst(),
            LearningEngineer(analytics_provider),
        ),
    )

    for employee in roster.employees:
        employee.identity.agent_id = uuid5(
            NAMESPACE_URL,
            f"https://auraai.local/employees/{employee.job_title}",
        )

    return roster
