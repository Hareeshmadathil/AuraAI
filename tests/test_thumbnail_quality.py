from company_missions import create_review_ready_production_package
from creative_quality.thumbnail_engine import ThumbnailQualityEngine


def test_all_thumbnail_concepts_are_scored_and_misleading_is_penalized() -> None:
    plan = create_review_ready_production_package().thumbnail_plan.model_copy(
        deep=True
    )
    plan.concepts[0] = plan.concepts[0].model_copy(
        update={"primary_text": "Guaranteed Instant Income"}
    )
    report = ThumbnailQualityEngine().analyze(plan)
    assert len(report.concepts) == len(plan.concepts)
    assert report.concepts[0].clickbait_risk > 50
    assert report.concepts[0].trust_score < 50
    assert report.recommended_concept_id != report.concepts[0].concept_id
    assert "actual performance" in report.ab_test_hypothesis
