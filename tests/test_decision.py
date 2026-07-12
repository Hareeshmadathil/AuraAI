"""
Tests for AuraAI's executive decision engine.
"""

import pytest

from core import (
    DecisionOutcome,
    DecisionRecord,
    DecisionReviewStatus,
    DecisionType,
    DepartmentName,
)


def test_executive_decision_lifecycle() -> None:
    """Verify evidence, decision, confirmation, actions, and review."""

    decision = DecisionRecord(
        title="Approve AuraAI's first content niche",
        decision_type=DecisionType.STRATEGIC,
        requires_user_confirmation=True,
    )

    decision.add_evidence(
        title="Audience demand",
        description=(
            "Research identified strong interest in AI productivity."
        ),
        source_type="research_report",
        reliability_score=0.9,
    )

    action = decision.add_next_action(
        description="Prepare the complete brand positioning report.",
        department=DepartmentName.STRATEGY,
    )

    decision.decide(
        outcome=DecisionOutcome.APPROVED,
        reasoning=(
            "The niche has strong demand, manageable competition, "
            "low production cost, and clear monetization paths."
        ),
        confidence_score=0.94,
    )

    assert decision.outcome == DecisionOutcome.APPROVED
    assert decision.is_final is True
    assert decision.confidence_percentage == 94.0
    assert decision.decided_at is not None
    assert len(decision.evidence) == 1

    decision.confirm_by_user()

    assert decision.user_confirmed is True

    action.mark_completed()

    assert decision.action_progress_percentage == 100.0

    decision.review(
        status=DecisionReviewStatus.SUCCESSFUL,
        notes=(
            "The approved niche produced stronger engagement than "
            "the initial target."
        ),
        actual_outcome={
            "engagement_target_met": True,
        },
    )

    assert (
        decision.review_status
        == DecisionReviewStatus.SUCCESSFUL
    )
    assert decision.reviewed_at is not None
    assert decision.actual_outcome[
        "engagement_target_met"
    ] is True


def test_final_decision_requires_reasoning() -> None:
    """Prevent unexplained executive decisions."""

    decision = DecisionRecord(
        title="Purchase premium AI video software",
        decision_type=DecisionType.FINANCIAL,
    )

    with pytest.raises(ValueError):
        decision.decide(
            outcome=DecisionOutcome.REJECTED,
            reasoning="",
            confidence_score=0.95,
        )


def test_paid_tool_decision_can_be_rejected() -> None:
    """Record AuraAI's revenue-first financial rule."""

    decision = DecisionRecord(
        title="Purchase premium voice generation service",
        decision_type=DecisionType.FINANCIAL,
    )

    decision.decide(
        outcome=DecisionOutcome.REJECTED,
        reasoning=(
            "Paid services are postponed until AuraAI starts "
            "generating income."
        ),
        confidence_score=1.0,
    )

    assert decision.outcome == DecisionOutcome.REJECTED
    assert decision.confidence_percentage == 100.0
    assert decision.is_final is True