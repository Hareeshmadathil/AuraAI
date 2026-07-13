"""Replaceable offline-first contracts for future quality providers."""

from __future__ import annotations

from typing import Protocol

from creative_quality.models import (
    FactualityReport,
    HookAnalysis,
    RetentionReport,
    StoryFlowReport,
    ThumbnailQualityReport,
)
from production.models import ProductionPackage, ThumbnailPlan, VideoScript


class HookReviewProvider(Protocol):
    def review_hook(self, script: VideoScript) -> HookAnalysis: ...


class StoryReviewProvider(Protocol):
    def review_story(self, script: VideoScript) -> StoryFlowReport: ...


class RetentionReviewProvider(Protocol):
    def review_retention(self, script: VideoScript) -> RetentionReport: ...


class ThumbnailReviewProvider(Protocol):
    def review_thumbnail(self, plan: ThumbnailPlan) -> ThumbnailQualityReport: ...


class FactualityReviewProvider(Protocol):
    def review_factuality(self, package: ProductionPackage) -> FactualityReport: ...
