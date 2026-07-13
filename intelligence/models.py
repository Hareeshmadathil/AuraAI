"""Typed outputs for AuraAI Intelligence Department v1."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field, field_validator

from core import AuraBaseModel, utc_now


class TrendDirection(StrEnum):
    """Deterministic directional classification for a topic."""

    EMERGING = "emerging"
    STEADY = "steady"
    CROWDED = "crowded"


class TrendReport(AuraBaseModel):
    report_id: UUID = Field(default_factory=uuid4)
    niche: str = Field(min_length=1, max_length=500)
    direction: TrendDirection
    opportunity_score: float = Field(ge=0, le=100)
    signals: list[str] = Field(min_length=1)
    risks: list[str] = Field(default_factory=list)
    sample_data: bool = True


class CompetitorReport(AuraBaseModel):
    report_id: UUID = Field(default_factory=uuid4)
    niche: str = Field(min_length=1, max_length=500)
    competitor_archetypes: list[str] = Field(min_length=1)
    content_gaps: list[str] = Field(min_length=1)
    differentiation_strategy: str = Field(min_length=1, max_length=3000)
    saturation_score: float = Field(ge=0, le=100)
    sample_data: bool = True


class AudiencePersona(AuraBaseModel):
    persona_id: UUID = Field(default_factory=uuid4)
    niche: str = Field(min_length=1, max_length=500)
    persona_name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=3000)
    goals: list[str] = Field(min_length=1)
    pain_points: list[str] = Field(min_length=1)
    objections: list[str] = Field(min_length=1)
    content_preferences: list[str] = Field(min_length=1)
    sample_data: bool = True


class SEOReport(AuraBaseModel):
    report_id: UUID = Field(default_factory=uuid4)
    niche: str = Field(min_length=1, max_length=500)
    primary_keyword: str = Field(min_length=1, max_length=500)
    secondary_keywords: list[str] = Field(min_length=1)
    search_intent: str = Field(min_length=1, max_length=1000)
    title_patterns: list[str] = Field(min_length=1)
    description_guidance: str = Field(min_length=1, max_length=3000)
    sample_data: bool = True


class ThumbnailAnalysis(AuraBaseModel):
    analysis_id: UUID = Field(default_factory=uuid4)
    niche: str = Field(min_length=1, max_length=500)
    concepts: list[str] = Field(min_length=1)
    recommended_concept: str = Field(min_length=1, max_length=1000)
    visual_hierarchy: list[str] = Field(min_length=1)
    clarity_score: float = Field(ge=0, le=100)
    warnings: list[str] = Field(default_factory=list)
    sample_data: bool = True


class HookAnalysis(AuraBaseModel):
    analysis_id: UUID = Field(default_factory=uuid4)
    niche: str = Field(min_length=1, max_length=500)
    hooks: list[str] = Field(min_length=1)
    recommended_hook: str = Field(min_length=1, max_length=1000)
    pacing_guidance: list[str] = Field(min_length=1)
    retention_risks: list[str] = Field(min_length=1)
    retention_score: float = Field(ge=0, le=100)
    sample_data: bool = True


class IntelligencePackage(AuraBaseModel):
    package_id: UUID = Field(default_factory=uuid4)
    mission_id: UUID | None = None
    workflow_id: UUID
    niche: str = Field(min_length=1, max_length=500)
    trend_report: TrendReport
    competitor_report: CompetitorReport
    audience_persona: AudiencePersona
    seo_report: SEOReport
    thumbnail_analysis: ThumbnailAnalysis
    hook_analysis: HookAnalysis
    deterministic: bool = True
    sample_data: bool = True
    warnings: list[str] = Field(default_factory=list)
    completed_at: datetime = Field(default_factory=utc_now)

    @field_validator("completed_at")
    @classmethod
    def completion_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Intelligence completion time must be timezone-aware.")
        return value
