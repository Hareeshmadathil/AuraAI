"""Authoritative Mission Control V1 domain contracts."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from core import AuraBaseModel, DepartmentName, TaskPriority, utc_now


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CONSEQUENTIAL = "consequential"


class MissionDifficulty(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MissionControlStatus(StrEnum):
    CREATED = "created"
    READY = "ready"
    RUNNING = "running"
    APPROVAL_REQUIRED = "approval_required"
    BLOCKED = "blocked"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    BLOCKED = "blocked"
    APPROVAL_REQUIRED = "approval_required"
    RETRY_PENDING = "retry_pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ApprovalState(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    REVOKED = "revoked"
    REVISION_REQUESTED = "revision_requested"


class ArtifactApprovalState(StrEnum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class MissionRecord(AuraBaseModel):
    mission_id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=1, max_length=250)
    objective: str = Field(min_length=1, max_length=5000)
    status: MissionControlStatus = MissionControlStatus.CREATED
    priority: TaskPriority = TaskPriority.NORMAL
    risk: RiskLevel = RiskLevel.LOW
    current_stage: str = Field(default="created", min_length=1, max_length=100)
    founder_owner: str = Field(min_length=1, max_length=150)
    founder_goal: str = Field(default="Not supplied", min_length=1, max_length=2000)
    expected_outcome: str = Field(default="Founder-reviewed mission output", min_length=1, max_length=3000)
    business_value: str = Field(default="Validated operational learning", min_length=1, max_length=3000)
    difficulty: MissionDifficulty = MissionDifficulty.MEDIUM
    estimated_execution_minutes: int = Field(default=30, ge=1, le=43200)
    required_departments: list[DepartmentName] = Field(default_factory=list)
    required_approvals: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    failure_criteria: list[str] = Field(default_factory=list)
    artifacts_expected: list[str] = Field(default_factory=list)
    mission_dependencies: list[str] = Field(default_factory=list)
    offline_execution: Literal[True] = True
    provider_requirements: list[str] = Field(default_factory=list)
    publishing_required: Literal[False] = False
    rendering_required: Literal[False] = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    mission_score: float = Field(default=0.0, ge=0.0, le=100.0)
    reasoning_summary: str = Field(default="Pending generation rationale", min_length=1, max_length=3000)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class TaskRecord(AuraBaseModel):
    task_id: UUID = Field(default_factory=uuid4)
    mission_id: UUID
    title: str = Field(min_length=1, max_length=250)
    department: DepartmentName
    assigned_agent_id: UUID | None = None
    dependencies: list[UUID] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    attempts: int = Field(default=0, ge=0)
    maximum_attempts: int = Field(default=3, ge=1, le=20)
    timeout_seconds: int = Field(default=300, ge=1, le=86400)
    retry_delay_seconds: int = Field(default=0, ge=0, le=86400)
    blocking_reason: str | None = Field(default=None, max_length=2000)
    idempotency_key: str = Field(min_length=1, max_length=200)
    payload: dict[str, Any] = Field(default_factory=dict)
    consequential: bool = False
    required_action: str | None = Field(default=None, max_length=150)
    required_artifact_hash: str | None = Field(
        default=None, pattern=r"^[a-f0-9]{64}$"
    )
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_dependencies(self) -> "TaskRecord":
        if self.task_id in self.dependencies:
            raise ValueError("A task cannot depend on itself.")
        if len(self.dependencies) != len(set(self.dependencies)):
            raise ValueError("Task dependencies must be unique.")
        if self.consequential and not self.required_action:
            raise ValueError("Consequential tasks require an approval action.")
        return self


class ArtifactRecord(AuraBaseModel):
    artifact_id: UUID = Field(default_factory=uuid4)
    mission_id: UUID
    task_id: UUID | None = None
    artifact_type: str = Field(min_length=1, max_length=100)
    location: str = Field(min_length=1, max_length=1000)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    version: int = Field(default=1, ge=1)
    provenance: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    approval_state: ArtifactApprovalState = ArtifactApprovalState.PENDING
    created_at: datetime = Field(default_factory=utc_now)


class EventRecord(AuraBaseModel):
    sequence: int = Field(default=0, ge=0)
    event_id: UUID = Field(default_factory=uuid4)
    mission_id: UUID | None = None
    task_id: UUID | None = None
    event_type: str = Field(min_length=1, max_length=150)
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=utc_now)


class ApprovalRequest(AuraBaseModel):
    approval_id: UUID = Field(default_factory=uuid4)
    mission_id: UUID
    task_id: UUID | None = None
    artifact_id: UUID | None = None
    requested_action: str = Field(min_length=1, max_length=150)
    risk: RiskLevel
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    state: ApprovalState = ApprovalState.PENDING
    approver: str | None = Field(default=None, max_length=150)
    reason: str | None = Field(default=None, max_length=2000)
    issued_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime
    decided_at: datetime | None = None

    @model_validator(mode="after")
    def validate_expiry(self) -> "ApprovalRequest":
        if self.expires_at <= self.issued_at:
            raise ValueError("Approval expiry must follow issue time.")
        return self


class DepartmentCommand(AuraBaseModel):
    command_id: UUID = Field(default_factory=uuid4)
    mission_id: UUID
    task_id: UUID
    department: DepartmentName
    assigned_agent_id: UUID | None = None
    operation: str = Field(min_length=1, max_length=150)
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1, max_length=200)


class DepartmentResult(AuraBaseModel):
    command_id: UUID
    mission_id: UUID
    task_id: UUID
    success: bool
    payload: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = Field(default=None, max_length=150)
    completed_at: datetime = Field(default_factory=utc_now)


class MissionControlProjection(AuraBaseModel):
    missions: list[MissionRecord]
    pending_approvals: list[ApprovalRequest]
    blocked_tasks: list[TaskRecord]
    recent_events: list[EventRecord]
    artifacts: list[ArtifactRecord]
    recent_mission_outcomes: list[dict[str, Any]] = Field(default_factory=list)
    generated_lessons: list[dict[str, Any]] = Field(default_factory=list)
    pending_lesson_approvals: list[dict[str, Any]] = Field(default_factory=list)
    lesson_influences: list[str] = Field(default_factory=list)
    system_health: str
