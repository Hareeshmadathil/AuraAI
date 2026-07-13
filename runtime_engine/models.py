"""Typed runtime projections and events for AuraAI coordination."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from core.constants import AgentStatus, DepartmentName, JobStatus, MissionStatus
from core.decision import DecisionRecord
from core.models import AuraBaseModel, utc_now


class RuntimeMode(StrEnum):
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    DEGRADED = "degraded"


class RuntimeEventType(StrEnum):
    RUNTIME_STARTED = "runtime_started"
    RUNTIME_STOPPED = "runtime_stopped"
    MISSION_REGISTERED = "mission_registered"
    MISSION_STARTED = "mission_started"
    MISSION_PAUSED = "mission_paused"
    MISSION_RESUMED = "mission_resumed"
    MISSION_COMPLETED = "mission_completed"
    MISSION_FAILED = "mission_failed"
    WORKFLOW_REGISTERED = "workflow_registered"
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    EMPLOYEE_STATUS_CHANGED = "employee_status_changed"
    DECISION_RECORDED = "decision_recorded"
    WARNING = "warning"
    SYSTEM_ERROR = "system_error"
    PRODUCTION_STAGE_STARTED = "production_stage_started"
    PRODUCTION_STAGE_COMPLETED = "production_stage_completed"
    PRODUCTION_STAGE_FAILED = "production_stage_failed"
    PRODUCTION_PACKAGE_READY = "production_package_ready"
    RENDER_REQUESTED = "render_requested"
    RENDER_STARTED = "render_started"
    CAPABILITY_CHECK_COMPLETED = "capability_check_completed"
    VOICE_RENDER_STARTED = "voice_render_started"
    VOICE_RENDER_COMPLETED = "voice_render_completed"
    SCENE_RENDER_STARTED = "scene_render_started"
    SCENE_RENDER_COMPLETED = "scene_render_completed"
    THUMBNAIL_RENDER_COMPLETED = "thumbnail_render_completed"
    SUBTITLE_EXPORT_COMPLETED = "subtitle_export_completed"
    LONG_FORM_RENDER_COMPLETED = "long_form_render_completed"
    SHORT_RENDER_COMPLETED = "short_render_completed"
    RENDER_VALIDATION_COMPLETED = "render_validation_completed"
    RENDER_COMPLETED = "render_completed"
    RENDER_FAILED = "render_failed"
    FOUNDER_REVIEW_REQUIRED = "founder_review_required"
    INTELLIGENCE_STARTED = "intelligence_started"
    INTELLIGENCE_STAGE_STARTED = "intelligence_stage_started"
    INTELLIGENCE_STAGE_COMPLETED = "intelligence_stage_completed"
    INTELLIGENCE_STAGE_FAILED = "intelligence_stage_failed"
    INTELLIGENCE_COMPLETED = "intelligence_completed"
    CREATIVE_QUALITY_STARTED = "creative_quality_started"
    HOOK_REVIEW_STARTED = "hook_review_started"
    HOOK_REVIEW_COMPLETED = "hook_review_completed"
    STORY_REVIEW_COMPLETED = "story_review_completed"
    RETENTION_REVIEW_COMPLETED = "retention_review_completed"
    MOTION_REVIEW_COMPLETED = "motion_review_completed"
    SUBTITLE_REVIEW_COMPLETED = "subtitle_review_completed"
    THUMBNAIL_REVIEW_COMPLETED = "thumbnail_review_completed"
    FACTUALITY_REVIEW_COMPLETED = "factuality_review_completed"
    CREATIVE_QUALITY_SCORED = "creative_quality_scored"
    REVISION_PLAN_CREATED = "revision_plan_created"
    REVISION_APPLIED = "revision_applied"
    CREATIVE_QUALITY_PASSED = "creative_quality_passed"
    CREATIVE_QUALITY_REVISION_REQUIRED = "creative_quality_revision_required"
    CREATIVE_QUALITY_BLOCKED = "creative_quality_blocked"
    FOUNDER_QUALITY_REVIEW_REQUIRED = "founder_quality_review_required"
    CREATIVE_QUALITY_COMPLETED = "creative_quality_completed"


class RuntimeEventSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class RuntimeEvent(AuraBaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    event_type: RuntimeEventType
    timestamp: datetime = Field(default_factory=utc_now)
    message: str = Field(min_length=1, max_length=5000)
    mission_id: UUID | None = None
    workflow_id: UUID | None = None
    task_id: UUID | None = None
    agent_id: UUID | None = None
    agent_name: str | None = None
    department: DepartmentName | None = None
    severity: RuntimeEventSeverity = RuntimeEventSeverity.INFO
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Runtime event timestamps must be timezone-aware.")
        return value


class RuntimeEmployeeState(AuraBaseModel):
    agent_id: UUID
    name: str
    job_title: str
    department: DepartmentName
    status: AgentStatus
    current_task_id: UUID | None = None
    current_task_title: str | None = None
    current_mission_id: UUID | None = None
    last_event_at: datetime | None = None
    error_message: str | None = None

    @field_validator("last_event_at")
    @classmethod
    def validate_last_event_at(cls, value: datetime | None) -> datetime | None:
        return _validate_aware(value)


class RuntimeMissionState(AuraBaseModel):
    mission_id: UUID
    title: str
    status: MissionStatus
    progress_percentage: float = Field(ge=0.0, le=100.0)
    active_workflow_id: UUID | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    paused_at: datetime | None = None
    error_message: str | None = None

    @field_validator("started_at", "completed_at", "paused_at")
    @classmethod
    def validate_mission_times(cls, value: datetime | None) -> datetime | None:
        return _validate_aware(value)


class RuntimeWorkflowState(AuraBaseModel):
    workflow_id: UUID
    mission_id: UUID | None = None
    name: str
    status: JobStatus
    progress_percentage: float = Field(ge=0.0, le=100.0)
    current_step_id: UUID | None = None
    current_step_name: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None

    @field_validator("started_at", "completed_at")
    @classmethod
    def validate_workflow_times(cls, value: datetime | None) -> datetime | None:
        return _validate_aware(value)


class RuntimeHealthComponent(AuraBaseModel):
    status: str = Field(min_length=1, max_length=100)
    message: str | None = Field(default=None, max_length=1000)


class RuntimeStatistics(AuraBaseModel):
    registered_missions: int = Field(ge=0)
    active_missions: int = Field(ge=0)
    completed_missions: int = Field(ge=0)
    failed_missions: int = Field(ge=0)
    registered_workflows: int = Field(ge=0)
    active_workflows: int = Field(ge=0)
    employees_working: int = Field(ge=0)
    employees_idle: int = Field(ge=0)
    pending_decisions: int = Field(ge=0)
    total_events: int = Field(ge=0)
    production_packages: int = Field(default=0, ge=0)
    render_exports: int = Field(default=0, ge=0)
    intelligence_packages: int = Field(default=0, ge=0)
    creative_quality_packages: int = Field(default=0, ge=0)


class RuntimeProductionState(AuraBaseModel):
    """Minimal truthful runtime projection for a production package."""

    package_id: UUID
    topic: str = Field(min_length=1, max_length=500)
    current_stage: str = Field(min_length=1, max_length=100)
    approval_status: str = Field(min_length=1, max_length=100)
    quality_score: float | None = Field(default=None, ge=0, le=100)
    sample_data: bool
    media_rendered: bool = False
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("updated_at")
    @classmethod
    def validate_updated_at(cls, value: datetime) -> datetime:
        validated = _validate_aware(value)
        if validated is None:
            raise ValueError("updated_at is required.")
        return validated


class RuntimeRenderState(AuraBaseModel):
    """Truthful runtime projection for a local review render."""

    production_package_id: UUID
    manifest_id: UUID
    status: str = Field(min_length=1, max_length=100)
    artifact_count: int = Field(ge=0)
    review_required: bool = True
    published: bool = False
    output_root: str = Field(min_length=1, max_length=2000)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def preserve_local_review_safety(self) -> "RuntimeRenderState":
        if self.published or not self.review_required:
            raise ValueError(
                "Runtime renders must remain unpublished and review-required."
            )
        return self

    @field_validator("updated_at")
    @classmethod
    def validate_render_time(cls, value: datetime) -> datetime:
        validated = _validate_aware(value)
        if validated is None:
            raise ValueError("updated_at is required.")
        return validated


class RuntimeIntelligenceState(AuraBaseModel):
    """Minimal runtime projection for an Intelligence package."""

    package_id: UUID
    mission_id: UUID | None = None
    workflow_id: UUID
    niche: str = Field(min_length=1, max_length=500)
    opportunity_score: float = Field(ge=0, le=100)
    retention_score: float = Field(ge=0, le=100)
    deterministic: bool = True
    report_count: int = Field(default=6, ge=0)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("updated_at")
    @classmethod
    def validate_intelligence_time(cls, value: datetime) -> datetime:
        validated = _validate_aware(value)
        if validated is None:
            raise ValueError("updated_at is required.")
        return validated


class RuntimeCreativeQualityState(AuraBaseModel):
    """Minimal runtime projection for one creative-quality package."""

    package_id: UUID
    production_package_id: UUID
    current_stage: str = Field(min_length=1, max_length=100)
    overall_score: float = Field(ge=0, le=100)
    gate_status: str = Field(min_length=1, max_length=100)
    blocker_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    revision_count: int = Field(ge=0)
    started_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = Field(default=None, max_length=5000)

    @field_validator("started_at", "completed_at")
    @classmethod
    def validate_quality_times(cls, value: datetime | None) -> datetime | None:
        return _validate_aware(value)


class RuntimeSnapshot(AuraBaseModel):
    mode: RuntimeMode
    generated_at: datetime = Field(default_factory=utc_now)
    statistics: RuntimeStatistics
    employees: list[RuntimeEmployeeState] = Field(default_factory=list)
    missions: list[RuntimeMissionState] = Field(default_factory=list)
    workflows: list[RuntimeWorkflowState] = Field(default_factory=list)
    decisions: list[DecisionRecord] = Field(default_factory=list)
    recent_events: list[RuntimeEvent] = Field(default_factory=list)
    system_health: dict[str, RuntimeHealthComponent] = Field(default_factory=dict)
    production_packages: list[RuntimeProductionState] = Field(default_factory=list)
    render_exports: list[RuntimeRenderState] = Field(default_factory=list)
    intelligence_packages: list[RuntimeIntelligenceState] = Field(
        default_factory=list
    )
    creative_quality_packages: list[RuntimeCreativeQualityState] = Field(
        default_factory=list
    )

    @field_validator("generated_at")
    @classmethod
    def validate_generated_at(cls, value: datetime) -> datetime:
        validated = _validate_aware(value)
        if validated is None:
            raise ValueError("generated_at is required.")
        return validated


def _validate_aware(value: datetime | None) -> datetime | None:
    """Validate optional runtime timestamps consistently."""

    if value is not None and (
        value.tzinfo is None or value.utcoffset() is None
    ):
        raise ValueError("Runtime timestamps must be timezone-aware.")
    return value
