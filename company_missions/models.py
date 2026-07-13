"""Typed models for AuraAI's deterministic niche discovery mission."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator

from agents.specialists import TrendCandidate, TrendOpportunity
from core import AuraBaseModel, ContentPlatform, DepartmentName


class NicheCandidateInput(AuraBaseModel):
    """Explicit, non-live candidate evidence supplied to the pipeline."""

    name: str = Field(min_length=1, max_length=250)
    description: str = Field(default="", max_length=5000)
    demand_score: float = Field(ge=0.0, le=100.0)
    trend_velocity_score: float = Field(ge=0.0, le=100.0)
    monetization_score: float = Field(ge=0.0, le=100.0)
    competition_score: float = Field(ge=0.0, le=100.0)
    production_difficulty_score: float = Field(ge=0.0, le=100.0)
    evidence: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)

    def to_trend_candidate(self) -> TrendCandidate:
        """Convert input into the existing Trend Hunter model."""

        return TrendCandidate.model_validate(self.model_dump())


class NicheDiscoveryInput(AuraBaseModel):
    """Complete deterministic input for one niche discovery run."""

    mission_title: str = Field(min_length=1, max_length=250)
    business_goal: str = Field(min_length=1, max_length=5000)
    target_market: str = Field(min_length=1, max_length=2000)
    preferred_platforms: list[ContentPlatform] = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)
    candidate_niches: list[NicheCandidateInput] = Field(min_length=1)


class NicheDiscoveryStageResult(AuraBaseModel):
    """Auditable result for one employee or coordination stage."""

    stage_name: str = Field(min_length=1, max_length=150)
    success: bool
    employee_name: str = Field(min_length=1, max_length=150)
    department: DepartmentName
    output: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime
    completed_at: datetime
    error: str | None = Field(default=None, max_length=5000)

    @field_validator("started_at", "completed_at")
    @classmethod
    def validate_timestamps(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Stage timestamps must be timezone-aware.")
        return value


class NicheDiscoveryResult(AuraBaseModel):
    """Final structured result of the niche discovery pipeline."""

    mission_id: UUID
    selected_niche: TrendOpportunity
    ranked_candidates: list[TrendOpportunity] = Field(min_length=1)
    research_plan_id: UUID
    strategy_summary: str = Field(min_length=1, max_length=5000)
    marketing_readiness: bool
    confidence_score: float = Field(ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)
    stages: list[NicheDiscoveryStageResult] = Field(min_length=1)
    completed_at: datetime

    @field_validator("completed_at")
    @classmethod
    def validate_completed_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Completion timestamp must be timezone-aware.")
        return value
