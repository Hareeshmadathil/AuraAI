"""Tests for AuraAI's SEO Specialist."""

import pytest

from agents.specialists import SEOKeywordCandidate, SEOSpecialist
from core import (
    ContentPlatform,
    DepartmentName,
    JobStatus,
    TaskRecord,
    ValidationError,
)


def build_candidates() -> list[SEOKeywordCandidate]:
    """Create deterministic keyword candidates for tests."""

    return [
        SEOKeywordCandidate(
            keyword="AI productivity for small business",
            relevance_score=95,
            search_intent_score=90,
            competition_score=35,
            monetization_score=88,
            platform_fit_score=92,
        ),
        SEOKeywordCandidate(
            keyword="productivity tips",
            relevance_score=75,
            search_intent_score=80,
            competition_score=85,
            monetization_score=60,
            platform_fit_score=78,
        ),
        SEOKeywordCandidate(
            keyword="small business AI tools",
            relevance_score=90,
            search_intent_score=86,
            competition_score=50,
            monetization_score=90,
            platform_fit_score=85,
        ),
    ]


def build_task(**overrides: object) -> TaskRecord:
    """Create a complete SEO task with optional input overrides."""

    input_data: dict[str, object] = {
        "topic": "Practical AI productivity",
        "target_audience": "Small business owners",
        "platform": ContentPlatform.YOUTUBE,
        "keyword_candidates": build_candidates(),
    }
    input_data.update(overrides)
    return TaskRecord(
        title="Create SEO plan",
        department=DepartmentName.MARKETING,
        input_data=input_data,
    )


def test_seo_specialist_ranks_keywords() -> None:
    """Rank the strongest keyword first with transparent scores."""

    recommendations = SEOSpecialist().rank_keywords(build_candidates())

    assert recommendations[0].rank == 1
    assert (
        recommendations[0].keyword
        == "AI productivity for small business"
    )
    assert recommendations[0].seo_score > recommendations[1].seo_score
    assert sum(recommendations[0].score_breakdown.values()) == (
        recommendations[0].seo_score
    )


def test_lower_competition_improves_score() -> None:
    """Reward the lower-competition candidate when other inputs match."""

    shared = {
        "relevance_score": 80,
        "search_intent_score": 80,
        "monetization_score": 80,
        "platform_fit_score": 80,
    }
    recommendations = SEOSpecialist().rank_keywords(
        [
            SEOKeywordCandidate(
                keyword="high competition",
                competition_score=90,
                **shared,
            ),
            SEOKeywordCandidate(
                keyword="low competition",
                competition_score=20,
                **shared,
            ),
        ]
    )

    assert recommendations[0].keyword == "low competition"
    assert recommendations[0].score_breakdown[
        "competition_advantage"
    ] > recommendations[1].score_breakdown["competition_advantage"]


def test_seo_specialist_base_employee_lifecycle() -> None:
    """Execute SEO planning through BaseEmployee lifecycle."""

    specialist = SEOSpecialist()
    task = build_task()

    specialist.accept_task(task)
    result = specialist.execute_current_task()

    assert specialist.department == DepartmentName.MARKETING
    assert result.success is True
    assert task.status == JobStatus.COMPLETED
    assert result.data["seo_plan"]["platform"] == "youtube"

    specialist.clear_current_task()
    assert specialist.current_task is None


def test_seo_specialist_rejects_invalid_platform() -> None:
    """Reject platform values outside ContentPlatform."""

    specialist = SEOSpecialist()
    task = build_task(platform="facebook")
    specialist.accept_task(task)
    result = specialist.execute_current_task()

    assert result.success is False
    assert task.status == JobStatus.FAILED
    assert "supported ContentPlatform" in result.message


def test_seo_specialist_rejects_missing_keyword_candidates() -> None:
    """Reject tasks without keyword candidates."""

    specialist = SEOSpecialist()

    with pytest.raises(ValidationError):
        specialist._parse_candidates(None)


def test_seo_plan_contains_expected_output() -> None:
    """Return all required deterministic SEO guidance."""

    plan = SEOSpecialist().create_seo_plan(
        topic="Practical AI productivity",
        target_audience="Small business owners",
        platform=ContentPlatform.TIKTOK,
        keyword_candidates=build_candidates(),
    )

    assert plan.ranked_keywords
    assert plan.recommended_primary_keyword
    assert plan.secondary_keywords
    assert plan.title_guidance
    assert plan.description_guidance
    assert plan.hashtag_guidance
    assert plan.platform_specific_notes
    assert plan.platform == ContentPlatform.TIKTOK
