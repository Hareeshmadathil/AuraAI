"""
Tests for AuraAI's company mission system.
"""

import pytest

from core.constants import (
    ApprovalStatus,
    DepartmentName,
    MissionStatus,
    TaskPriority,
)
from core.mission import MissionRecord


def test_mission_lifecycle() -> None:
    """Verify approval, planning, execution, and completion."""

    mission = MissionRecord(
        title="Discover AuraAI's first profitable niche",
        description=(
            "Research and recommend a sustainable niche, target "
            "audience, brand position, and monetization strategy."
        ),
        priority=TaskPriority.HIGH,
        lead_department=DepartmentName.STRATEGY,
    )

    objective = mission.add_objective(
        description="Recommend one validated niche.",
        success_metric="Executive-approved niche recommendation",
        target_value="1 approved niche",
    )

    assert mission.status == MissionStatus.DRAFT
    assert mission.approval_status == ApprovalStatus.PENDING
    assert mission.progress_percentage == 0.0

    mission.submit_for_approval()

    assert mission.status == MissionStatus.PENDING_APPROVAL

    mission.approve(
        "Approved because the mission supports AuraAI's "
        "revenue-first roadmap."
    )

    assert mission.status == MissionStatus.APPROVED
    assert mission.is_approved is True

    mission.begin_planning()
    assert mission.status == MissionStatus.PLANNING

    mission.activate()
    assert mission.status == MissionStatus.ACTIVE
    assert mission.started_at is not None

    objective.mark_achieved()

    assert mission.progress_percentage == 100.0

    mission.complete()

    assert mission.status == MissionStatus.COMPLETED
    assert mission.is_terminal is True
    assert mission.completed_at is not None


def test_mission_cannot_complete_with_open_objectives() -> None:
    """Prevent false completion when objectives remain unfinished."""

    mission = MissionRecord(
        title="Prepare channel branding",
        description="Create and approve the new brand identity.",
        requires_user_approval=False,
    )

    mission.add_objective(
        description="Approve the final brand name."
    )

    mission.begin_planning()
    mission.activate()

    with pytest.raises(ValueError):
        mission.complete()


def test_mission_rejection_requires_reason() -> None:
    """Require a meaningful explanation for rejected missions."""

    mission = MissionRecord(
        title="Purchase premium video software",
        description=(
            "Consider a paid tool before AuraAI generates revenue."
        ),
    )

    with pytest.raises(ValueError):
        mission.reject("")

    mission.reject(
        "Rejected because AuraAI has not started generating income."
    )

    assert mission.status == MissionStatus.REJECTED
    assert mission.approval_status == ApprovalStatus.REJECTED
    assert mission.is_terminal is True