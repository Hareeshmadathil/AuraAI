"""Typed Mission Execution Engine V1 domain models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from core.constants import ApprovalStatus, DepartmentName, TaskPriority
from core.models import AuraBaseModel, utc_now


class MissionCapability(StrEnum):
    """Mission capabilities supported by the deterministic V1 engine."""

    CONTENT_PIPELINE = "content_pipeline"
    RESEARCH = "research"
    SEO = "seo"
    SCRIPT = "script"


class MissionExecutionStatus(StrEnum):
    """Strict execution stages for Mission Execution Engine V1."""

    CREATED = "created"
    PLANNING = "planning"
    RESEARCH = "research"
    SEO = "seo"
    SCRIPT = "script"
    FOUNDER_REVIEW = "founder_review"
    COMPLETED = "completed"
    FAILED = "failed"


class MissionArtifactType(StrEnum):
    """Metadata-only outputs produced during V1 mission execution."""

    RESEARCH = "research"
    KEYWORDS = "keywords"
    SCRIPT = "script"
    QUALITY_REPORT = "quality_report"
    APPROVAL_NOTES = "approval_notes"


class MissionArtifactStatus(StrEnum):
    """Lifecycle status for immutable mission artifact versions."""

    CURRENT = "current"
    SUPERSEDED = "superseded"


class MissionAssignee(AuraBaseModel):
    """One employee explicitly assigned to a mission."""

    employee_id: UUID
    employee_name: str = Field(min_length=1, max_length=150)
    department: DepartmentName
    assigned_at: datetime = Field(default_factory=utc_now)


class MissionArtifact(AuraBaseModel):
    """Metadata for an employee output; content is stored elsewhere."""

    artifact_id: UUID = Field(default_factory=uuid4)
    mission_id: UUID
    artifact_type: MissionArtifactType
    name: str = Field(min_length=1, max_length=250)
    summary: str = Field(default="", max_length=2000)
    produced_by_employee_id: UUID | None = None
    producer: str = Field(default="AuraAI", min_length=1, max_length=150)
    stage: MissionExecutionStatus | None = None
    version_number: int = Field(default=1, ge=1)
    parent_artifact_id: UUID | None = None
    content_hash: str = Field(
        default="0" * 64,
        pattern=r"^[a-f0-9]{64}$",
    )
    status: MissionArtifactStatus = MissionArtifactStatus.CURRENT
    founder_review_required: bool = True
    metadata_reference: str | None = Field(default=None, max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class MissionHistoryEntry(AuraBaseModel):
    """Immutable audit entry for creation, transition, or approval activity."""

    history_id: UUID = Field(default_factory=uuid4)
    from_status: MissionExecutionStatus | None = None
    to_status: MissionExecutionStatus
    note: str = Field(default="", max_length=2000)
    action: str = Field(default="state_transition", max_length=100)
    metadata: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=utc_now)


_PROGRESS_BY_STATUS = MappingProxyType({
    MissionExecutionStatus.CREATED: 0.0,
    MissionExecutionStatus.PLANNING: 10.0,
    MissionExecutionStatus.RESEARCH: 30.0,
    MissionExecutionStatus.SEO: 50.0,
    MissionExecutionStatus.SCRIPT: 70.0,
    MissionExecutionStatus.FOUNDER_REVIEW: 90.0,
    MissionExecutionStatus.COMPLETED: 100.0,
    MissionExecutionStatus.FAILED: 0.0,
})


class Mission(AuraBaseModel):
    """Execution backbone for one deterministic AuraAI business mission."""

    mission_id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=1, max_length=250)
    objective: str = Field(min_length=1, max_length=5000)
    capability: MissionCapability
    priority: TaskPriority = TaskPriority.NORMAL
    status: MissionExecutionStatus = MissionExecutionStatus.CREATED
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    founder_approval_state: ApprovalStatus = ApprovalStatus.PENDING
    assigned_departments: list[DepartmentName] = Field(default_factory=list)
    assigned_employees: list[MissionAssignee] = Field(default_factory=list)
    produced_artifacts: list[MissionArtifact] = Field(default_factory=list)
    history: list[MissionHistoryEntry] = Field(default_factory=list)
    failure_reason: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_completion_approval(self) -> "Mission":
        """Reject inconsistent approval, assignment, and artifact state."""

        if self.updated_at < self.created_at:
            raise ValueError("Mission updated_at cannot precede created_at.")
        if (
            self.status == MissionExecutionStatus.COMPLETED
            and self.founder_approval_state != ApprovalStatus.APPROVED
        ):
            raise ValueError(
                "A mission cannot be completed without founder approval."
            )
        employee_ids = [
            employee.employee_id for employee in self.assigned_employees
        ]
        if len(employee_ids) != len(set(employee_ids)):
            raise ValueError("Mission employee assignments must be unique.")
        if len(self.assigned_departments) != len(
            set(self.assigned_departments)
        ):
            raise ValueError("Mission department assignments must be unique.")
        if any(
            artifact.mission_id != self.mission_id
            for artifact in self.produced_artifacts
        ):
            raise ValueError("Mission artifacts must belong to the mission.")
        return self

    @property
    def progress_percentage(self) -> float:
        """Return deterministic stage-based progress for dashboard display."""

        return _PROGRESS_BY_STATUS[self.status]

    @property
    def is_terminal(self) -> bool:
        """Return whether no further state transition is allowed."""

        return self.status in {
            MissionExecutionStatus.COMPLETED,
            MissionExecutionStatus.FAILED,
        }
