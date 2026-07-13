"""AuraAI deterministic Content Quality Engine v1."""

from creative_quality.models import *
from creative_quality.quality_gate import CreativeQualityGateEvaluator
from creative_quality.revision_engine import DeterministicRevisionEngine
from creative_quality.scoring import (
    DEFAULT_QUALITY_WEIGHTS,
    CreativeQualityScorer,
    QualityScoreBreakdown,
)

__all__ = [
    "CreativeQualityGateEvaluator",
    "CreativeQualityPipeline",
    "CreativeQualityScorer",
    "DEFAULT_QUALITY_WEIGHTS",
    "DeterministicRevisionEngine",
    "QualityScoreBreakdown",
    "create_creative_quality_pipeline",
]


def __getattr__(name: str):
    """Load pipeline exports lazily to avoid employee-package cycles."""

    if name in {"CreativeQualityPipeline", "create_creative_quality_pipeline"}:
        from creative_quality.pipeline import (
            CreativeQualityPipeline,
            create_creative_quality_pipeline,
        )

        return {
            "CreativeQualityPipeline": CreativeQualityPipeline,
            "create_creative_quality_pipeline": create_creative_quality_pipeline,
        }[name]
    raise AttributeError(name)
