"""Deterministic calculations for manually supplied performance data."""

from __future__ import annotations

from analytics.models import (
    AnalyticsReport,
    LearningReport,
    ManualPerformanceMetrics,
    MetricComparison,
)
from distribution.models import DistributionPackage


class DeterministicAnalyticsProvider:
    """Use transparent formulas and thresholds; perform no ML training."""

    def analyze(self, metrics: ManualPerformanceMetrics) -> AnalyticsReport:
        """Derive stable rates from explicit metrics."""

        views = max(metrics.views, 1)
        engagement = (
            metrics.likes + metrics.comments + metrics.shares
        ) / views * 100
        observations = [
            "Metrics were supplied manually and were not fetched from a platform."
        ]
        if metrics.click_through_rate < 4:
            observations.append("CTR is below the internal 4% review threshold.")
        if metrics.retention_percentage < 40:
            observations.append(
                "Retention is below the internal 40% review threshold."
            )
        return AnalyticsReport(
            metrics=metrics,
            engagement_rate=round(engagement, 2),
            subscriber_conversion_rate=round(
                metrics.subscribers_gained / views * 100,
                2,
            ),
            share_rate=round(metrics.shares / views * 100, 2),
            returning_viewer_rate=round(
                metrics.returning_viewers / views * 100,
                2,
            ),
            top_traffic_source=self._top(metrics.traffic_sources),
            top_country=self._top(metrics.countries),
            top_device=self._top(metrics.devices),
            observations=observations,
        )

    def learn(
        self,
        package: DistributionPackage,
        report: AnalyticsReport,
    ) -> LearningReport:
        """Compare internal heuristics with observed metrics deterministically."""

        metrics = report.metrics
        comparisons = [
            self._comparison(
                "hook",
                package.predicted_hook_score or 50,
                min(100, metrics.click_through_rate * 12.5),
            ),
            self._comparison(
                "retention",
                package.predicted_retention_score or 50,
                metrics.retention_percentage,
            ),
            self._comparison(
                "thumbnail",
                package.predicted_thumbnail_score or 50,
                min(100, metrics.click_through_rate * 12.5),
            ),
            self._comparison(
                "overall_quality",
                package.predicted_quality_score or 50,
                self._observed_quality(report),
            ),
        ]
        weak = [item.dimension for item in comparisons if item.difference < -10]
        recommendations = [
            f"Review {dimension.replace('_', ' ')} assumptions before the next run."
            for dimension in weak
        ] or [
            "Preserve the current structure and test one controlled change next."
        ]
        return LearningReport(
            distribution_package_id=package.package_id,
            analytics_report_id=report.report_id,
            comparisons=comparisons,
            improvement_recommendations=recommendations,
            future_hook_suggestions=[
                "Lead with a specific, truthful audience problem in the first line."
            ],
            thumbnail_observations=[
                self._threshold_note(
                    metrics.click_through_rate,
                    4,
                    "Thumbnail/title pairing needs a clarity review.",
                    "Thumbnail/title pairing cleared the internal CTR threshold.",
                )
            ],
            retention_observations=[
                self._threshold_note(
                    metrics.retention_percentage,
                    40,
                    "Shorten setup and advance evidence earlier.",
                    "Retention cleared the internal review threshold.",
                )
            ],
            seo_observations=[
                (
                    "Top supplied traffic source: "
                    f"{report.top_traffic_source or 'unknown'}."
                )
            ],
            upload_timing_observations=[
                (
                    f"The supplied upload hour was {metrics.upload_hour_utc}:00 UTC; "
                    "compare at least three manual uploads before inferring timing."
                    if metrics.upload_hour_utc is not None
                    else "Upload time was not supplied; no timing inference was made."
                )
            ],
        )

    @staticmethod
    def _comparison(
        dimension: str,
        predicted: float,
        observed: float,
    ) -> MetricComparison:
        difference = round(observed - predicted, 2)
        direction = "above" if difference >= 0 else "below"
        return MetricComparison(
            dimension=dimension,
            predicted_score=round(predicted, 2),
            observed_score=round(observed, 2),
            difference=difference,
            interpretation=(
                f"Observed proxy is {abs(difference):.2f} points {direction} the "
                "internal heuristic; this is directional, not causal."
            ),
        )

    @staticmethod
    def _observed_quality(report: AnalyticsReport) -> float:
        metrics = report.metrics
        return round(
            min(100, metrics.click_through_rate * 12.5) * 0.25
            + metrics.retention_percentage * 0.5
            + min(100, report.engagement_rate * 10) * 0.25,
            2,
        )

    @staticmethod
    def _top(values: dict[str, int]) -> str | None:
        return max(values, key=lambda key: (values[key], key)) if values else None

    @staticmethod
    def _threshold_note(
        value: float,
        threshold: float,
        below: str,
        above: str,
    ) -> str:
        return below if value < threshold else above
