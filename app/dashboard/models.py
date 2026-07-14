"""Typed read models for the AuraAI command-center dashboard."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import Field

from core.constants import (
    AgentStatus,
    DecisionOutcome,
    DecisionType,
    DepartmentName,
    JobStatus,
    MissionStatus,
    TaskPriority,
)
from core.models import AuraBaseModel, utc_now
from intelligence.models import IntelligencePackage
from creative_quality.models import CreativeQualityPackage
from analytics.models import AnalyticsReport, LearningReport
from distribution.models import DistributionPackage
from mission_engine.models import MissionExecutionStatus
from providers.models import ProviderState


class DashboardMode(StrEnum):
    """Explicit source mode for a dashboard snapshot."""

    EMPTY = "empty"
    DEMO = "demo"
    INJECTED = "injected"


class EmployeeGroup(StrEnum):
    """Organizational level used by dashboard roster views."""

    EXECUTIVE = "executive"
    DIRECTOR = "director"
    SPECIALIST = "specialist"


_SPECIALIST_DIRECTOR_TITLES = frozenset({"Story Director"})


def classify_employee_group(
    department: DepartmentName,
    job_title: str,
) -> EmployeeGroup:
    """Classify formal company level while preserving specialist titles."""

    if department == DepartmentName.EXECUTIVE:
        return EmployeeGroup.EXECUTIVE
    if (
        job_title.endswith("Director")
        and job_title not in _SPECIALIST_DIRECTOR_TITLES
    ):
        return EmployeeGroup.DIRECTOR
    return EmployeeGroup.SPECIALIST


class ActivityEventType(StrEnum):
    """Supported dashboard activity categories."""

    EMPLOYEE = "employee"
    MISSION = "mission"
    DECISION = "decision"
    WORKFLOW = "workflow"
    SYSTEM = "system"


class SystemHealthStatus(StrEnum):
    """Overall state reported by the local dashboard."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class DashboardMetric(AuraBaseModel):
    """One high-level command-center metric."""

    key: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=150)
    value: int = Field(ge=0)
    description: str = Field(default="", max_length=500)


class EmployeeStatusSummary(AuraBaseModel):
    """Dashboard-safe employee identity and runtime state."""

    agent_id: UUID
    name: str
    job_title: str
    department: DepartmentName
    status: AgentStatus
    enabled: bool
    group: EmployeeGroup


class MissionArtifactSummary(AuraBaseModel):
    """Dashboard-safe metadata for one mission-produced artifact."""

    artifact_id: UUID
    artifact_type: str
    name: str
    summary: str = ""


class MissionStatusSummary(AuraBaseModel):
    """Dashboard-safe mission lifecycle summary."""

    mission_id: UUID
    title: str
    description: str = ""
    status: MissionStatus | MissionExecutionStatus
    priority: TaskPriority
    lead_department: DepartmentName | None = None
    progress_percentage: float = Field(ge=0.0, le=100.0)
    objective: str = ""
    capability: str = ""
    founder_approval_state: str = ""
    assigned_departments: list[DepartmentName] = Field(default_factory=list)
    assigned_employees: list[str] = Field(default_factory=list)
    generated_artifacts: list[MissionArtifactSummary] = Field(
        default_factory=list
    )


class WorkflowStatusSummary(AuraBaseModel):
    """Dashboard-safe workflow lifecycle summary."""

    workflow_id: UUID
    name: str
    description: str = ""
    status: JobStatus
    progress_percentage: float = Field(ge=0.0, le=100.0)
    task_count: int = Field(ge=0)


class ExecutiveDecisionSummary(AuraBaseModel):
    """Dashboard-safe executive decision summary."""

    decision_id: UUID
    title: str
    decision_type: DecisionType
    outcome: DecisionOutcome
    decision_maker_name: str
    requires_user_confirmation: bool
    user_confirmed: bool
    created_at: datetime


class ActivityEventSummary(AuraBaseModel):
    """One recent event derived from explicitly supplied state."""

    event_id: str = Field(min_length=1, max_length=200)
    event_type: ActivityEventType
    title: str = Field(min_length=1, max_length=250)
    detail: str = Field(min_length=1, max_length=1000)
    occurred_at: datetime


class SystemHealthSummary(AuraBaseModel):
    """Operational health details supplied to the dashboard."""

    status: SystemHealthStatus = SystemHealthStatus.HEALTHY
    web_service_operational: bool = True
    test_status: str = Field(default="not_supplied", max_length=100)
    tests_passed: int | None = Field(default=None, ge=0)
    tests_total: int | None = Field(default=None, ge=0)
    message: str = Field(
        default="Local dashboard service is operational.",
        max_length=1000,
    )


class ProductionStatusSummary(AuraBaseModel):
    """Dashboard-safe summary of one structured production package."""

    package_id: UUID
    brand_name: str
    topic: str
    working_title: str
    current_stage: str
    completed_stages: list[str] = Field(default_factory=list)
    selected_style: str
    content_brief_summary: str
    script_word_count: int = Field(ge=0)
    storyboard_scene_count: int = Field(ge=0)
    visual_request_count: int = Field(ge=0)
    voice_segment_count: int = Field(ge=0)
    thumbnail_concepts: list[str] = Field(default_factory=list)
    short_form_counts: dict[str, int] = Field(default_factory=dict)
    subtitle_status: str
    assembly_status: str
    quality_score: float | None = Field(default=None, ge=0, le=100)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    founder_approval_status: str
    sample_data: bool
    media_rendered: bool = False


class RenderArtifactSummary(AuraBaseModel):
    """Safe metadata for one downloadable local review artifact."""

    artifact_id: UUID
    artifact_type: str
    file_name: str = Field(min_length=1, max_length=500)
    mime_type: str = Field(min_length=1, max_length=200)
    size_bytes: int = Field(ge=0)
    duration_seconds: float | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    checksum_sha256: str
    review_required: bool = True
    published: bool = False


class RenderStatusSummary(AuraBaseModel):
    """Dashboard projection for the explicit local render result."""

    production_package_id: UUID
    manifest_id: UUID
    status: str
    engine: str
    artifacts: list[RenderArtifactSummary] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    review_required: bool = True
    publish_allowed: bool = False
    sample_data: bool = True


class DashboardSnapshot(AuraBaseModel):
    """Immutable point-in-time view of AuraAI operating state."""

    mode: DashboardMode = DashboardMode.EMPTY
    data_label: str = "EMPTY STATE"
    generated_at: datetime = Field(default_factory=utc_now)
    active_missions: int = Field(default=0, ge=0)
    employees_working: int = Field(default=0, ge=0)
    employees_idle: int = Field(default=0, ge=0)
    pending_decisions: int = Field(default=0, ge=0)
    active_workflows: int = Field(default=0, ge=0)
    employee_status_counts: dict[AgentStatus, int] = Field(
        default_factory=dict
    )
    metrics: list[DashboardMetric] = Field(default_factory=list)
    employees: list[EmployeeStatusSummary] = Field(default_factory=list)
    executives: list[EmployeeStatusSummary] = Field(default_factory=list)
    directors: list[EmployeeStatusSummary] = Field(default_factory=list)
    specialists: list[EmployeeStatusSummary] = Field(default_factory=list)
    missions: list[MissionStatusSummary] = Field(default_factory=list)
    workflows: list[WorkflowStatusSummary] = Field(default_factory=list)
    recent_decisions: list[ExecutiveDecisionSummary] = Field(
        default_factory=list
    )
    activity: list[ActivityEventSummary] = Field(default_factory=list)
    system_health: SystemHealthSummary = Field(
        default_factory=SystemHealthSummary
    )
    production: ProductionStatusSummary | None = None
    render: RenderStatusSummary | None = None
    intelligence: IntelligencePackage | None = None
    niche_discovery: dict[str, Any] | None = None
    creative_quality: CreativeQualityPackage | None = None
    distribution: DistributionPackage | None = None
    analytics: AnalyticsReport | None = None
    learning: LearningReport | None = None
    providers: ProviderState = Field(default_factory=ProviderState)
