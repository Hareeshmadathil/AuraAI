"""Explicit founder approval, rejection, and revision behavior."""

from company_missions.real_content_pilot import run_deterministic_real_content_pilot
from core import ApprovalStatus
from mission_engine import MissionExecutionStatus


def test_founder_approval_is_required_then_completes_content_only() -> None:
    pilot, result = run_deterministic_real_content_pilot()
    assert result.mission.status == MissionExecutionStatus.FOUNDER_REVIEW
    assert result.mission.founder_approval_state == ApprovalStatus.PENDING

    approved = pilot.founder_review.approve(
        result,
        notes="Approved as a content mission; rendering remains separate.",
    )
    assert approved.mission.status == MissionExecutionStatus.COMPLETED
    assert approved.mission.founder_approval_state == ApprovalStatus.APPROVED
    assert "rendering" in approved.founder_review_artifact.recommended_action


def test_rejection_preserves_artifacts_and_revision_stays_in_review() -> None:
    pilot, result = run_deterministic_real_content_pilot()
    revised = pilot.founder_review.request_revision(
        result, notes="Clarify the second section."
    )
    assert revised.mission.status == MissionExecutionStatus.FOUNDER_REVIEW
    assert revised.founder_review_artifact.review_status.value == "revision_requested"

    second_pilot, second = run_deterministic_real_content_pilot()
    artifact_count = len(second.mission.produced_artifacts)
    rejected = second_pilot.founder_review.reject(
        second, reason="Evidence needs founder-supplied sources."
    )
    assert rejected.mission.status == MissionExecutionStatus.FAILED
    assert len(rejected.mission.produced_artifacts) == artifact_count
    assert rejected.mission.founder_approval_state == ApprovalStatus.REJECTED
