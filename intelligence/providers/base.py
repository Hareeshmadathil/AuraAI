"""Provider contract for deterministic Intelligence analysis."""

from __future__ import annotations

from typing import Protocol

from intelligence.models import (
    AudiencePersona,
    CompetitorReport,
    HookAnalysis,
    SEOReport,
    ThumbnailAnalysis,
    TrendReport,
)


class IntelligenceProvider(Protocol):
    """Interface implemented without requiring credentials or network calls."""

    def analyze_trends(self, niche: str) -> TrendReport: ...
    def analyze_competitors(self, niche: str) -> CompetitorReport: ...
    def build_audience_persona(self, niche: str) -> AudiencePersona: ...
    def build_seo_report(self, niche: str) -> SEOReport: ...
    def analyze_thumbnail(self, niche: str) -> ThumbnailAnalysis: ...
    def analyze_hooks(self, niche: str) -> HookAnalysis: ...
