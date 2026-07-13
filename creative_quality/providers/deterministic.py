"""Deterministic implementations of Creative Quality provider contracts."""

from creative_quality.factuality_engine import FactualityEngine
from creative_quality.hook_engine import HookEngine
from creative_quality.models import (
    FactualityReport,
    HookAnalysis,
    RetentionReport,
    StoryFlowReport,
    ThumbnailQualityReport,
)
from creative_quality.retention_engine import RetentionEngine
from creative_quality.story_engine import StoryEngine
from creative_quality.thumbnail_engine import ThumbnailQualityEngine
from production.models import ProductionPackage, ThumbnailPlan, VideoScript


class DeterministicCreativeQualityProvider:
    """Compose pure local engines behind one injectable provider."""

    def __init__(self) -> None:
        self.hooks = HookEngine()
        self.stories = StoryEngine()
        self.retention = RetentionEngine()
        self.thumbnails = ThumbnailQualityEngine()
        self.factuality = FactualityEngine()

    def review_hook(self, script: VideoScript) -> HookAnalysis:
        return self.hooks.analyze(script)

    def review_story(self, script: VideoScript) -> StoryFlowReport:
        return self.stories.analyze(script)

    def review_retention(self, script: VideoScript) -> RetentionReport:
        return self.retention.analyze(script)

    def review_thumbnail(self, plan: ThumbnailPlan) -> ThumbnailQualityReport:
        return self.thumbnails.analyze(plan)

    def review_factuality(self, package: ProductionPackage) -> FactualityReport:
        return self.factuality.analyze(package)
