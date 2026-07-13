"""Manual analytics import and deterministic learning."""

from typing import Any

from analytics.models import (
    AnalyticsReport,
    LearningReport,
    ManualPerformanceMetrics,
    MetricComparison,
)


def __getattr__(name: str) -> Any:
    """Load pipelines lazily so typed analytics models stay import-safe."""

    if name in {
        "AnalyticsPipeline",
        "LearningPipeline",
        "create_analytics_pipelines",
    }:
        from analytics.pipeline import (
            AnalyticsPipeline,
            LearningPipeline,
            create_analytics_pipelines,
        )

        return {
            "AnalyticsPipeline": AnalyticsPipeline,
            "LearningPipeline": LearningPipeline,
            "create_analytics_pipelines": create_analytics_pipelines,
        }[name]
    raise AttributeError(name)


__all__ = [
    "AnalyticsPipeline",
    "AnalyticsReport",
    "LearningPipeline",
    "LearningReport",
    "ManualPerformanceMetrics",
    "MetricComparison",
    "create_analytics_pipelines",
]
