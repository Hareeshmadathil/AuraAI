"""Creative Quality reuse and gating tests."""

import pytest

from company_missions.real_content_pilot import (
    RealContentPilotResult,
    run_deterministic_real_content_pilot,
)
from core import ValidationError
from creative_quality.models import QualityGateStatus


def test_quality_package_is_registered_and_original_script_preserved() -> None:
    pilot, result = run_deterministic_real_content_pilot()

    assert result.quality_artifact.overall_score > 0
    assert result.quality_artifact.revision_count <= 1
    scripts = [
        item
        for item in pilot.artifact_store.list_all()
        if item.__class__.__name__ == "ScriptArtifact"
    ]
    assert scripts[0].version_number == 1


def test_quality_blocker_prevents_founder_approval() -> None:
    pilot, result = run_deterministic_real_content_pilot()
    blocked = result.quality_artifact.model_copy(
        update={
            "gate_status": QualityGateStatus.BLOCKED,
            "blocking_issues": ["Unverified high-risk claim"],
        }
    )
    blocked_result = RealContentPilotResult.model_validate(
        result.model_copy(update={"quality_artifact": blocked})
    )

    with pytest.raises(ValidationError, match="blockers"):
        pilot.founder_review.approve(blocked_result, notes="Approve")
