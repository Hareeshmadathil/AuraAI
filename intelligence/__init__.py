"""Public interfaces for AuraAI Intelligence Department v1."""

from intelligence.models import (
    AudiencePersona,
    CompetitorReport,
    HookAnalysis,
    IntelligencePackage,
    SEOReport,
    ThumbnailAnalysis,
    TrendDirection,
    TrendReport,
)

__all__ = [
    "AudiencePersona",
    "CompetitorReport",
    "HookAnalysis",
    "IntelligencePackage",
    "IntelligencePipeline",
    "SEOReport",
    "ThumbnailAnalysis",
    "TrendDirection",
    "TrendReport",
    "create_intelligence_pipeline",
]


def __getattr__(name: str):
    """Load pipeline orchestration lazily to keep model imports cycle-free."""

    if name in {"IntelligencePipeline", "create_intelligence_pipeline"}:
        from intelligence.pipeline import (
            IntelligencePipeline,
            create_intelligence_pipeline,
        )

        return {
            "IntelligencePipeline": IntelligencePipeline,
            "create_intelligence_pipeline": create_intelligence_pipeline,
        }[name]
    raise AttributeError(name)
