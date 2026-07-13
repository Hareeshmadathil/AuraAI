import pytest

from creative_quality.models import QualityDimension
from creative_quality.scoring import CreativeQualityScorer


def test_exact_weighted_score_and_breakdown() -> None:
    scorer = CreativeQualityScorer()
    values = {dimension: 80 for dimension in QualityDimension}
    result = scorer.calculate(values)
    assert result.overall == 80
    assert round(sum(result.contributions.values()), 2) == 80
    assert "does not predict" in result.heuristic_notice


def test_invalid_weights_are_rejected() -> None:
    with pytest.raises(ValueError):
        CreativeQualityScorer({dimension: 0.1 for dimension in QualityDimension})
