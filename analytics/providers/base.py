"""Provider-neutral manual analytics contract."""

from __future__ import annotations

from typing import Protocol

from analytics.models import AnalyticsReport, LearningReport, ManualPerformanceMetrics
from distribution.models import DistributionPackage


class AnalyticsProvider(Protocol):
    """Analyze founder-supplied values without network access or training."""

    def analyze(self, metrics: ManualPerformanceMetrics) -> AnalyticsReport: ...

    def learn(
        self,
        package: DistributionPackage,
        report: AnalyticsReport,
    ) -> LearningReport: ...
