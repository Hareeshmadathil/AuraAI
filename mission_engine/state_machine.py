"""Deterministic state transitions for Mission Execution Engine V1."""

from __future__ import annotations

from types import MappingProxyType

from core.constants import ApprovalStatus
from core.exceptions import ValidationError
from mission_engine.models import Mission, MissionExecutionStatus


_ALLOWED_TRANSITIONS = MappingProxyType(
    {
        MissionExecutionStatus.CREATED: frozenset(
            {MissionExecutionStatus.PLANNING, MissionExecutionStatus.FAILED}
        ),
        MissionExecutionStatus.PLANNING: frozenset(
            {MissionExecutionStatus.RESEARCH, MissionExecutionStatus.FAILED}
        ),
        MissionExecutionStatus.RESEARCH: frozenset(
            {MissionExecutionStatus.SEO, MissionExecutionStatus.FAILED}
        ),
        MissionExecutionStatus.SEO: frozenset(
            {MissionExecutionStatus.SCRIPT, MissionExecutionStatus.FAILED}
        ),
        MissionExecutionStatus.SCRIPT: frozenset(
            {
                MissionExecutionStatus.FOUNDER_REVIEW,
                MissionExecutionStatus.FAILED,
            }
        ),
        MissionExecutionStatus.FOUNDER_REVIEW: frozenset(
            {MissionExecutionStatus.COMPLETED, MissionExecutionStatus.FAILED}
        ),
        MissionExecutionStatus.COMPLETED: frozenset(),
        MissionExecutionStatus.FAILED: frozenset(),
    }
)


class MissionStateMachine:
    """Validate transitions without mutating mission state."""

    @staticmethod
    def allowed_targets(
        status: MissionExecutionStatus,
    ) -> frozenset[MissionExecutionStatus]:
        """Return the immutable target set for one current state."""

        return _ALLOWED_TRANSITIONS[status]

    @classmethod
    def validate_transition(
        cls,
        mission: Mission,
        target: MissionExecutionStatus,
    ) -> None:
        """Raise a typed validation error for an invalid transition."""

        if target not in cls.allowed_targets(mission.status):
            raise ValidationError(
                f"Mission cannot transition from {mission.status.value} "
                f"to {target.value}.",
                error_code="INVALID_MISSION_TRANSITION",
                details={
                    "mission_id": str(mission.mission_id),
                    "from_status": mission.status.value,
                    "to_status": target.value,
                },
            )
        if (
            target == MissionExecutionStatus.COMPLETED
            and mission.founder_approval_state != ApprovalStatus.APPROVED
        ):
            raise ValidationError(
                "Founder approval is required before mission completion.",
                error_code="FOUNDER_APPROVAL_REQUIRED",
                details={"mission_id": str(mission.mission_id)},
            )
