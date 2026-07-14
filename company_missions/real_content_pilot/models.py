"""Aggregate and audit models for the Real Content Pilot."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator

from core import AuraBaseModel, utc_now
from mission_engine import Mission, MissionExecutionStatus

from company_missions.real_content_pilot.artifacts import (
    CreativeQualityArtifact,
    FounderReviewArtifact,
    ResearchArtifact,
    SEOArtifact,
    ScriptArtifact,
)


class PilotStageStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    AWAITING_FOUNDER = "awaiting_founder"


class PilotStageResult(AuraBaseModel):
    stage: MissionExecutionStatus
    status: PilotStageStatus
    employee_names: list[str] = Field(default_factory=list)
    artifact_id: str | None = None
    safe_error_code: str | None = None
    started_at: datetime
    completed_at: datetime

    @field_validator("started_at", "completed_at")
    @classmethod
    def timestamps_are_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Stage timestamps must be timezone-aware.")
        return value


class ProviderStageUsage(AuraBaseModel):
    stage: MissionExecutionStatus
    provider: str
    fallback_used: bool
    request_count: int = Field(default=0, ge=0, le=1)


class RealContentPilotResult(AuraBaseModel):
    mission: Mission
    research_artifact: ResearchArtifact
    seo_artifact: SEOArtifact
    script_artifact: ScriptArtifact
    quality_artifact: CreativeQualityArtifact
    founder_review_artifact: FounderReviewArtifact
    stage_results: list[PilotStageResult] = Field(min_length=1)
    runtime_snapshot: dict[str, Any] | None = None
    provider_usage_summary: list[ProviderStageUsage] = Field(default_factory=list)
    completed_at: datetime | None = None

    @field_validator("completed_at")
    @classmethod
    def completion_is_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and (
            value.tzinfo is None or value.utcoffset() is None
        ):
            raise ValueError("completed_at must be timezone-aware.")
        return value


def stage_result(
    stage: MissionExecutionStatus,
    status: PilotStageStatus,
    employees: list[str],
    *,
    artifact_id: str | None = None,
    safe_error_code: str | None = None,
) -> PilotStageResult:
    """Create a deterministic-shape stage result with safe timestamps."""

    now = utc_now()
    return PilotStageResult(
        stage=stage,
        status=status,
        employee_names=employees,
        artifact_id=artifact_id,
        safe_error_code=safe_error_code,
        started_at=now,
        completed_at=now,
    )
