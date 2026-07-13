import pytest

from intelligence.models import IntelligencePackage, TrendReport
from intelligence.pipeline import create_intelligence_pipeline
from intelligence.providers import DeterministicIntelligenceProvider


def test_deterministic_provider_repeats_semantic_values() -> None:
    provider = DeterministicIntelligenceProvider()
    first = provider.analyze_trends("Responsible AI workflows")
    second = provider.analyze_trends("Responsible AI workflows")

    assert first.opportunity_score == second.opportunity_score
    assert first.direction == second.direction
    assert first.signals == second.signals
    assert first.report_id != second.report_id


def test_pipeline_output_validates_as_typed_package() -> None:
    result = create_intelligence_pipeline().run("Responsible AI workflows")
    package = IntelligencePackage.model_validate(
        result.data["intelligence_package"]
    )

    assert isinstance(package.trend_report, TrendReport)
    assert package.deterministic is True
    assert package.completed_at.tzinfo is not None


def test_report_scores_are_bounded() -> None:
    with pytest.raises(ValueError):
        TrendReport(
            niche="test",
            direction="steady",
            opportunity_score=101,
            signals=["sample"],
        )
