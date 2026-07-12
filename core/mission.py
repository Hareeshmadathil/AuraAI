"""
Mission models for AuraAI Creator OS.

A mission represents a high-level company objective received from the
user or created by AuraAI leadership. Missions are reviewed, approved,
planned, converted into workflows, executed by departments, and closed
only after their success criteria have been evaluated.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from core.constants import (
    ApprovalStatus,
    DepartmentName,
    MissionStatus,
    TaskPriority,
)
from core.models import AuraBaseModel, utc_now


_TERMINAL_MISSION_STATUSES = {
    MissionStatus.COMPLETED,
    MissionStatus.FAILED,
    MissionStatus.REJECTED,
    MissionStatus.CANCELLED,
}


class MissionObjective(AuraBaseModel):
    """One measurable objective belonging to a company mission."""

    objective_id: UUID = Field(default_factory=uuid4)

    description: str = Field(
        min_length=1,
        max_length=2000,
    )

    success_metric: str = Field(
        default="",
        max_length=1000,
    )

    target_value: str | None = Field(
        default=None,
        max_length=500,
    )

    achieved: bool = False

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def mark_achieved(self) -> None:
        """Mark this objective as achieved."""

        self.achieved = True
        self.updated_at = utc_now()

    def reopen(self) -> None:
        """Mark this objective as not yet achieved."""

        self.achieved = False
        self.updated_at = utc_now()


class MissionRecord(AuraBaseModel):
    """
    High-level business mission managed by AuraAI leadership.

    A mission may create multiple workflows and tasks, but it remains
    focused on the final business outcome rather than implementation
    details.
    """

    mission_id: UUID = Field(default_factory=uuid4)

    title: str = Field(
        min_length=1,
        max_length=250,
    )

    description: str = Field(
        min_length=1,
        max_length=10000,
    )

    requested_by: str = Field(
        default="Hareesh",
        min_length=1,
        max_length=150,
    )

    priority: TaskPriority = TaskPriority.NORMAL

    status: MissionStatus = MissionStatus.DRAFT

    approval_status: ApprovalStatus = ApprovalStatus.PENDING

    requires_user_approval: bool = True

    owner_agent_id: UUID | None = None

    lead_department: DepartmentName | None = None

    objectives: list[MissionObjective] = Field(default_factory=list)

    workflow_ids: list[UUID] = Field(default_factory=list)

    context: dict[str, Any] = Field(default_factory=dict)

    decision_notes: list[str] = Field(default_factory=list)

    rejection_reason: str | None = Field(
        default=None,
        max_length=5000,
    )

    failure_reason: str | None = Field(
        default=None,
        max_length=5000,
    )

    created_at: datetime = Field(default_factory=utc_now)
    approved_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_approval_configuration(self) -> "MissionRecord":
        """Keep approval fields logically consistent."""

        if not self.requires_user_approval:
            if self.approval_status == ApprovalStatus.PENDING:
                self.approval_status = ApprovalStatus.NOT_REQUIRED

        if (
            self.status == MissionStatus.APPROVED
            and self.approval_status
            not in {
                ApprovalStatus.APPROVED,
                ApprovalStatus.NOT_REQUIRED,
            }
        ):
            raise ValueError(
                "An approved mission must also have an approved "
                "or not-required approval status."
            )

        return self

    @property
    def is_terminal(self) -> bool:
        """Return whether the mission has reached a final state."""

        return self.status in _TERMINAL_MISSION_STATUSES

    @property
    def is_approved(self) -> bool:
        """Return whether the mission may proceed to planning."""

        return self.approval_status in {
            ApprovalStatus.APPROVED,
            ApprovalStatus.NOT_REQUIRED,
        }

    @property
    def objectives_completed(self) -> int:
        """Return the number of achieved objectives."""

        return sum(
            1
            for objective in self.objectives
            if objective.achieved
        )

    @property
    def progress_percentage(self) -> float:
        """
        Return objective-based mission progress.

        Missions without objectives report zero progress until an
        objective is defined.
        """

        if not self.objectives:
            return 0.0

        return round(
            (
                self.objectives_completed
                / len(self.objectives)
            )
            * 100,
            2,
        )

    def submit_for_approval(self) -> None:
        """Move a draft mission into the approval queue."""

        if self.status != MissionStatus.DRAFT:
            raise ValueError(
                "Only draft missions can be submitted for approval."
            )

        self.status = MissionStatus.PENDING_APPROVAL
        self.approval_status = ApprovalStatus.PENDING
        self.updated_at = utc_now()

    def approve(self, note: str | None = None) -> None:
        """Approve the mission for planning and execution."""

        if self.is_terminal:
            raise ValueError(
                "A terminal mission cannot be approved."
            )

        self.approval_status = ApprovalStatus.APPROVED
        self.status = MissionStatus.APPROVED
        self.approved_at = utc_now()
        self.rejection_reason = None
        self.updated_at = utc_now()

        if note:
            self.add_decision_note(note)

    def reject(self, reason: str) -> None:
        """Reject the mission before execution."""

        clean_reason = reason.strip()

        if not clean_reason:
            raise ValueError(
                "A rejection reason is required."
            )

        if self.status in {
            MissionStatus.ACTIVE,
            MissionStatus.COMPLETED,
        }:
            raise ValueError(
                "An active or completed mission cannot be rejected."
            )

        self.approval_status = ApprovalStatus.REJECTED
        self.status = MissionStatus.REJECTED
        self.rejection_reason = clean_reason
        self.updated_at = utc_now()

    def begin_planning(self) -> None:
        """Move an approved mission into the planning stage."""

        if not self.is_approved:
            raise ValueError(
                "The mission must be approved before planning."
            )

        if self.is_terminal:
            raise ValueError(
                "A terminal mission cannot enter planning."
            )

        self.status = MissionStatus.PLANNING
        self.updated_at = utc_now()

    def activate(self) -> None:
        """Start execution of a planned mission."""

        if not self.is_approved:
            raise ValueError(
                "The mission must be approved before activation."
            )

        if self.status not in {
            MissionStatus.APPROVED,
            MissionStatus.PLANNING,
            MissionStatus.PAUSED,
        }:
            raise ValueError(
                "The mission cannot be activated from its current "
                "status."
            )

        self.status = MissionStatus.ACTIVE
        self.started_at = self.started_at or utc_now()
        self.updated_at = utc_now()

    def pause(self) -> None:
        """Pause an active mission."""

        if self.status != MissionStatus.ACTIVE:
            raise ValueError(
                "Only active missions can be paused."
            )

        self.status = MissionStatus.PAUSED
        self.updated_at = utc_now()

    def complete(self) -> None:
        """
        Mark the mission as completed.

        All defined objectives must be achieved first.
        """

        if self.status not in {
            MissionStatus.ACTIVE,
            MissionStatus.PAUSED,
        }:
            raise ValueError(
                "Only active or paused missions can be completed."
            )

        incomplete_objectives = [
            objective
            for objective in self.objectives
            if not objective.achieved
        ]

        if incomplete_objectives:
            raise ValueError(
                "All mission objectives must be achieved before "
                "completion."
            )

        self.status = MissionStatus.COMPLETED
        self.completed_at = utc_now()
        self.failure_reason = None
        self.updated_at = utc_now()

    def fail(self, reason: str) -> None:
        """Mark the mission as failed."""

        clean_reason = reason.strip()

        if not clean_reason:
            raise ValueError(
                "A failure reason is required."
            )

        if self.is_terminal:
            raise ValueError(
                "A terminal mission cannot fail again."
            )

        self.status = MissionStatus.FAILED
        self.failure_reason = clean_reason
        self.completed_at = utc_now()
        self.updated_at = utc_now()

    def cancel(self, reason: str | None = None) -> None:
        """Cancel a non-terminal mission."""

        if self.is_terminal:
            raise ValueError(
                "A terminal mission cannot be cancelled."
            )

        self.status = MissionStatus.CANCELLED
        self.completed_at = utc_now()
        self.updated_at = utc_now()

        if reason:
            self.add_decision_note(
                f"Mission cancelled: {reason.strip()}"
            )

    def add_objective(
        self,
        *,
        description: str,
        success_metric: str = "",
        target_value: str | None = None,
    ) -> MissionObjective:
        """Create and attach a measurable mission objective."""

        objective = MissionObjective(
            description=description,
            success_metric=success_metric,
            target_value=target_value,
        )

        self.objectives.append(objective)
        self.updated_at = utc_now()

        return objective

    def add_workflow(self, workflow_id: UUID) -> None:
        """Attach a workflow identifier to the mission."""

        if workflow_id not in self.workflow_ids:
            self.workflow_ids.append(workflow_id)
            self.updated_at = utc_now()

    def add_decision_note(self, note: str) -> None:
        """Store an executive decision note."""

        clean_note = note.strip()

        if not clean_note:
            raise ValueError(
                "Decision notes cannot be empty."
            )

        self.decision_notes.append(clean_note)
        self.updated_at = utc_now()