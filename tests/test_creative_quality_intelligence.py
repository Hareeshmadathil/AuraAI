"""Regression coverage for Creative Quality Intelligence V2."""

import pytest

from company_missions import create_review_ready_production_package
from creative_quality.intelligence import CreativeQualityIntelligence
from creative_quality.models import (
    CreativeQualityIssue,
    CreativeQualityPackage,
    QualityDepartment,
    QualityDimension,
    QualitySeverity,
)
from creative_quality.pipeline import create_creative_quality_pipeline


def _quality_package() -> CreativeQualityPackage:
    result = create_creative_quality_pipeline().run(
        create_review_ready_production_package()
    )
    return CreativeQualityPackage.model_validate(
        result.data["creative_quality_package"]
    )


def test_breakdown_preserves_score_and_accounts_for_every_weight() -> None:
    quality = _quality_package()
    breakdown = quality.quality_breakdown

    assert breakdown is not None
    assert breakdown.overall_score == quality.scores.overall
    assert {item.department for item in breakdown.departments} == set(
        QualityDepartment
    )
    assert sum(item.weight for item in breakdown.departments) == pytest.approx(1)
    assert {
        dimension
        for department in breakdown.departments
        for dimension in department.contributing_dimensions
    } == set(QualityDimension)


def test_every_department_reports_decision_intelligence() -> None:
    breakdown = _quality_package().quality_breakdown

    assert breakdown is not None
    assert all(item.recommendations for item in breakdown.departments)
    assert all(item.suggested_employee for item in breakdown.departments)
    assert all(isinstance(item.passed, bool) for item in breakdown.departments)
    assert {item.suggested_employee for item in breakdown.departments} >= {
        "Hook Architect",
        "Story Director",
        "Thumbnail Psychologist",
    }
    assert breakdown.recommendations
    assert breakdown.estimated_score_after_revision >= breakdown.overall_score


def test_blocking_issues_are_sorted_high_to_medium_to_low() -> None:
    quality = _quality_package()
    issues = [
        CreativeQualityIssue(
            dimension=dimension,
            severity=severity,
            title=f"{severity.value} issue",
            description="Founder-visible issue.",
            affected_reference=severity.value,
            remediation="Resolve before approval.",
            blocking=True,
        )
        for dimension, severity in (
            (QualityDimension.HOOK, QualitySeverity.LOW),
            (QualityDimension.STORY, QualitySeverity.HIGH),
            (QualityDimension.RETENTION, QualitySeverity.MEDIUM),
        )
    ]

    report = CreativeQualityIntelligence().build(
        quality.model_copy(update={"issues": issues})
    )

    assert [item.severity for item in report.blocking_issues] == [
        QualitySeverity.HIGH,
        QualitySeverity.MEDIUM,
        QualitySeverity.LOW,
    ]


def test_breakdown_serialization_round_trip_is_strict() -> None:
    breakdown = _quality_package().quality_breakdown

    assert breakdown is not None
    parsed = type(breakdown).model_validate(breakdown.model_dump(mode="json"))
    assert parsed == breakdown
