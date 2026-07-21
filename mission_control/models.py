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
    FOUNDER_REVIEW_APPROVED = "founder_review_approved"
    RENDERING = "rendering"
    PUBLISHING_PREPARATION = "publishing_preparation"
    AWAITING_PUBLISH_APPROVAL = "awaiting_publish_approval"
    READY_FOR_MANUAL_PUBLISH = "ready_for_manual_publish"
    AWAITING_MANUAL_PUBLISH_CONFIRMATION = "awaiting_manual_publish_confirmation"
    PUBLISHED_CONFIRMED = "published_confirmed"
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
    SUPERSEDED = "superseded"


class ArtifactApprovalState(StrEnum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class AttemptStatus(StrEnum):
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class FailureClassification(StrEnum):
    NONE = "none"
    RETRYABLE = "retryable"
    NON_RETRYABLE = "non_retryable"
    MANUAL_ONLY = "manual_only"
    FOUNDER_REVIEW_REQUIRED = "founder_review_required"
    INTERRUPTED = "interrupted"
    EXHAUSTED = "exhausted"


class RetryMode(StrEnum):
    EXPLICIT = "explicit"
    MANUAL_ONLY = "manual_only"
    NEVER = "never"


class CheckpointKind(StrEnum):
    PROGRESS = "progress"
    EMPLOYEE_STATE = "employee_state"
    ARTIFACT_REFERENCE = "artifact_reference"


class CheckpointResumability(StrEnum):
    RESUMABLE = "resumable"
    RESTART_REQUIRED = "restart_required"
    MANUAL_ONLY = "manual_only"


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
    publishing_generation: int = Field(default=0, ge=0)
    publishing_generation_key: str | None = Field(default=None, max_length=200)
    required_publish_destinations: list[str] = Field(default_factory=list)
    blocking_reason: str | None = Field(default=None, max_length=2000)
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
    retry_mode: RetryMode = RetryMode.EXPLICIT
    backoff_multiplier: float = Field(default=1.0, ge=1.0, le=100.0)
    next_eligible_at: datetime | None = None
    last_failure_classification: FailureClassification = (
        FailureClassification.NONE
    )
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
    subject_type: str | None = Field(default=None, max_length=100)
    subject_id: UUID | None = None
    requested_action: str = Field(min_length=1, max_length=150)
    risk: RiskLevel
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    state: ApprovalState = ApprovalState.PENDING
    approver: str | None = Field(default=None, max_length=150)
    reason: str | None = Field(default=None, max_length=2000)
    issued_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime
    decided_at: datetime | None = None
    checkpoint_id: UUID | None = None
    correlation_id: UUID = Field(default_factory=uuid4)
    causation_id: UUID | None = None

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
    retryable: bool = True
    completed_at: datetime = Field(default_factory=utc_now)


class ExecutionAttempt(AuraBaseModel):
    attempt_id: UUID = Field(default_factory=uuid4)
    mission_id: UUID
    task_id: UUID
    employee_id: UUID
    attempt_number: int = Field(ge=1)
    starting_task_state: TaskStatus
    status: AttemptStatus = AttemptStatus.STARTED
    failure_classification: FailureClassification = FailureClassification.NONE
    error_summary: str | None = Field(default=None, max_length=2000)
    checkpoint_id: UUID | None = None
    result_reference: str | None = Field(default=None, max_length=500)
    retry_eligible: bool = False
    correlation_id: UUID = Field(default_factory=uuid4)
    causation_id: UUID | None = None
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None


class TaskCheckpoint(AuraBaseModel):
    checkpoint_id: UUID = Field(default_factory=uuid4)
    mission_id: UUID
    task_id: UUID
    attempt_id: UUID
    sequence: int = Field(ge=1)
    kind: CheckpointKind
    payload: dict[str, Any] = Field(default_factory=dict)
    artifact_reference: str | None = Field(default=None, max_length=1000)
    payload_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    producer_employee_id: UUID
    resumability: CheckpointResumability
    schema_version: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=utc_now)


class RenderJobStatus(StrEnum):
    PENDING = "pending"
    RENDERING = "rendering"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class PublishingQueueStatus(StrEnum):
    AWAITING_PUBLISH_APPROVAL = "awaiting_publish_approval"
    READY_FOR_MANUAL_PUBLISH = "ready_for_manual_publish"
    AWAITING_MANUAL_PUBLISH_CONFIRMATION = "awaiting_manual_publish_confirmation"
    PUBLISHED_CONFIRMED = "published_confirmed"
    REJECTED = "rejected"
    REVISION_REQUESTED = "revision_requested"


class RenderJob(AuraBaseModel):
    job_id: UUID = Field(default_factory=uuid4)
    mission_id: UUID
    task_id: UUID
    status: RenderJobStatus = RenderJobStatus.PENDING
    progress_message: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

import uuid
import hashlib
import json

AURA_QUEUE_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "queue.auraai.com")
AURA_ARTIFACT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "artifacts.auraai.com")

def normalize_destination(dest: str) -> str:
    d = dest.strip().lower()
    if not d:
        raise ValueError("Destination cannot be empty")
    return d

def normalize_destinations(destinations: list[str]) -> list[str]:
    normalized = set()
    for d in destinations:
        normalized.add(normalize_destination(d))
    return sorted(list(normalized))

def generate_manifest_hash(manifest: "PublishingManifest") -> str:
    encoded = json.dumps(
        manifest.model_dump(mode="json", exclude_none=True),
        sort_keys=True,
        separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

def generate_queue_identity(mission_id: UUID, task_id: UUID, destination: str, content_version: int, manifest_hash: str) -> UUID:
    canonical_string = f"{mission_id}:{task_id}:{destination.strip().lower()}:{content_version}:{manifest_hash}"
    return uuid.uuid5(AURA_QUEUE_NAMESPACE, canonical_string)

def generate_manifest_artifact_identity(mission_id: UUID, task_id: UUID, destination: str, content_version: int, manifest_hash: str) -> UUID:
    canonical_string = f"{mission_id}:{task_id}:{destination.strip().lower()}:{content_version}:{manifest_hash}"
    return uuid.uuid5(AURA_ARTIFACT_NAMESPACE, canonical_string)

class PublishingManifest(AuraBaseModel):
    schema_version: int = 1
    mission_id: UUID
    task_id: UUID
    render_job_id: UUID | None = None
    destination: str
    media_artifact_id: UUID
    thumbnail_artifact_id: UUID | None = None
    source_artifact_ids: list[UUID] = Field(default_factory=list)
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=5000)
    caption: str = Field(min_length=1, max_length=5000)
    hashtags: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    language: str = Field(default="English", max_length=100)
    content_version: int = Field(default=1, ge=1)


class PublishingQueueItem(AuraBaseModel):
    queue_item_id: UUID = Field(default_factory=uuid4)
    mission_id: UUID
    manifest_id: UUID
    source_package_id: UUID
    target_platforms: list[str]
    destination: str = Field(default="legacy", min_length=1, max_length=150)
    generation: int = Field(default=1, ge=1)
    content_version: int = Field(default=1, ge=1)
    is_active: bool = Field(default=True)
    superseded_by: UUID | None = None
    manifest_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: PublishingQueueStatus = PublishingQueueStatus.AWAITING_PUBLISH_APPROVAL
    approval_id: UUID | None = None
    founder_note: str | None = Field(default=None, max_length=2000)
    manual_confirmation_note: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class PublicationRecord(AuraBaseModel):
    publication_id: UUID = Field(default_factory=uuid4)
    mission_id: UUID
    queue_item_id: UUID
    destination: str = Field(min_length=1, max_length=150)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    external_url: str | None = Field(default=None, max_length=2000)
    external_post_id: str | None = Field(default=None, max_length=150)
    confirmation_note: str | None = Field(default=None, max_length=2000)
    published_by_actor: str = Field(min_length=1, max_length=150)
    confirmed_at: datetime = Field(default_factory=utc_now)

class AuraDomainError(Exception):
    """Base domain exception."""

class ItemNotFoundError(AuraDomainError):
    pass

class StaleContentError(AuraDomainError):
    pass

class ConflictingDecisionError(AuraDomainError):
    pass

class MalformedCommandError(AuraDomainError):
    pass

class MismatchError(AuraDomainError):
    pass


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
    attempts: list[ExecutionAttempt] = Field(default_factory=list)
    checkpoints: list[TaskCheckpoint] = Field(default_factory=list)
    render_jobs: list[RenderJob] = Field(default_factory=list)
    publishing_queue: list[PublishingQueueItem] = Field(default_factory=list)
