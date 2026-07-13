from datetime import datetime

import pytest
from pydantic import ValidationError

from creative_quality.models import (
    CreativeQualityIssue,
    CreativeQualityScores,
    QualityDimension,
    QualitySeverity,
)


def test_scores_reject_values_outside_internal_scale() -> None:
    values = {field: 80 for field in CreativeQualityScores.model_fields}
    values["hook"] = 101
    with pytest.raises(ValidationError):
        CreativeQualityScores(**values)


def test_blocking_issue_requires_actionable_remediation() -> None:
    with pytest.raises(ValidationError):
        CreativeQualityIssue(
            dimension=QualityDimension.FACTUALITY,
            severity=QualitySeverity.BLOCKING,
            title="Unsupported guarantee",
            description="No evidence was supplied.",
            affected_reference="claim-1",
            blocking=True,
        )


def test_quality_timestamps_reject_naive_values() -> None:
    from creative_quality.models import HookAnalysis

    with pytest.raises(ValidationError):
        HookAnalysis(
            original_hook="A truthful hook",
            hook_type="problem-led",
            clarity_score=80,
            curiosity_score=80,
            relevance_score=80,
            credibility_score=80,
            emotional_score=80,
            first_five_seconds_score=80,
            first_fifteen_seconds_score=80,
            improved_hook="A better truthful hook",
            reviewed_at=datetime(2026, 1, 1),
        )
