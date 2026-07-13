"""Transparent internal heuristic scoring for creative quality."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import Field

from core import AuraBaseModel
from creative_quality.models import CreativeQualityScores, QualityDimension


DEFAULT_QUALITY_WEIGHTS: dict[QualityDimension, float] = {
    QualityDimension.HOOK: 0.15,
    QualityDimension.STORY: 0.12,
    QualityDimension.PACING: 0.10,
    QualityDimension.RETENTION: 0.15,
    QualityDimension.CLARITY: 0.08,
    QualityDimension.MOTION: 0.06,
    QualityDimension.SUBTITLES: 0.06,
    QualityDimension.THUMBNAIL: 0.10,
    QualityDimension.FACTUALITY: 0.08,
    QualityDimension.TRUST: 0.04,
    QualityDimension.CALL_TO_ACTION: 0.03,
    QualityDimension.PRODUCTION_COMPLETENESS: 0.03,
}


class QualityScoreBreakdown(AuraBaseModel):
    """Auditable score inputs, weights, contributions, and total."""

    values: dict[QualityDimension, float]
    weights: dict[QualityDimension, float]
    contributions: dict[QualityDimension, float]
    overall: float = Field(ge=0, le=100)
    heuristic_notice: str = (
        "Internal deterministic quality heuristic; it does not predict views, "
        "click-through rate, retention, subscribers, or revenue."
    )


class CreativeQualityScorer:
    """Calculate consistent weighted quality scores without randomness."""

    def __init__(
        self,
        weights: Mapping[QualityDimension, float] | None = None,
    ) -> None:
        self.weights = dict(weights or DEFAULT_QUALITY_WEIGHTS)
        self._validate_weights()

    def calculate(
        self,
        values: Mapping[QualityDimension, float],
    ) -> QualityScoreBreakdown:
        """Return an explicit rounded weighted score breakdown."""

        missing = set(self.weights) - set(values)
        extra = set(values) - set(self.weights)
        if missing or extra:
            raise ValueError("Score values must match every configured dimension.")
        normalized = {
            dimension: self._score(value) for dimension, value in values.items()
        }
        contributions = {
            dimension: round(normalized[dimension] * weight, 4)
            for dimension, weight in self.weights.items()
        }
        return QualityScoreBreakdown(
            values=normalized,
            weights=self.weights,
            contributions=contributions,
            overall=round(sum(contributions.values()), 2),
        )

    def to_scores(
        self,
        values: Mapping[QualityDimension, float],
    ) -> CreativeQualityScores:
        """Build the public score model from one breakdown."""

        result = self.calculate(values)
        data = {dimension.value: score for dimension, score in result.values.items()}
        return CreativeQualityScores(**data, overall=result.overall)

    def _validate_weights(self) -> None:
        if set(self.weights) != set(QualityDimension):
            raise ValueError(
                "Weights must define every quality dimension exactly once."
            )
        if any(weight <= 0 or weight > 1 for weight in self.weights.values()):
            raise ValueError(
                "Quality weights must be greater than zero and at most one."
            )
        if abs(sum(self.weights.values()) - 1.0) > 1e-9:
            raise ValueError("Quality weights must sum to 1.0.")

    @staticmethod
    def _score(value: float) -> float:
        numeric = float(value)
        if numeric < 0 or numeric > 100:
            raise ValueError("Quality scores must be between 0 and 100.")
        return round(numeric, 2)
