"""Typed contracts for the founder-controlled first content mission."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from core import AuraBaseModel, ContentPlatform, utc_now
from creative_quality.models import CreativeQualityPackage
from mission_engine import Mission, MissionExecutionStatus
from production.models import ProductionPackage, VideoStyle
from providers.models import ProviderCapability

from company_missions.real_content_pilot.models import RealContentPilotResult
from company_missions.real_content_pilot.artifacts import ScriptArtifact


class EvidenceClassification(StrEnum):
    FOUNDER_SUPPLIED_FACT = "founder_supplied_fact"
    FOUNDER_SUPPLIED_SOURCE = "founder_supplied_source"
    PROVIDER_SYNTHESIS = "provider_synthesis"
    DETERMINISTIC_ASSUMPTION = "deterministic_assumption"
    UNVERIFIED_CLAIM = "unverified_claim"
    VERIFICATION_REQUIRED = "verification_required"


class EvidenceItem(AuraBaseModel):
    classification: EvidenceClassification
    summary: str = Field(min_length=1, max_length=3000)
    verification_required: bool = True


class FirstContentMissionInput(AuraBaseModel):
    """Credential-free founder input for one controlled mission."""

    mission_title: str = Field(min_length=1, max_length=250)
    objective: str = Field(min_length=1, max_length=5000)
    topic: str = Field(min_length=1, max_length=500)
    target_audience: str = Field(min_length=1, max_length=2000)
    audience_problem: str = Field(min_length=1, max_length=3000)
    audience_promise: str = Field(min_length=1, max_length=3000)
    content_goal: str = Field(min_length=1, max_length=3000)
    primary_platform: ContentPlatform = ContentPlatform.YOUTUBE
    language: str = Field(min_length=1, max_length=100)
    tone: str = Field(min_length=1, max_length=500)
    preferred_video_style: VideoStyle | None = None
    target_duration_seconds: int = Field(ge=60, le=1800)
    primary_call_to_action: str = Field(min_length=1, max_length=1000)
    source_notes: list[str] = Field(default_factory=list)
    source_references: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    prohibited_claims: list[str] = Field(default_factory=list)
    preferred_keywords: list[str] = Field(default_factory=list)
    preferred_channel_direction: str | None = Field(default=None, max_length=1000)
    allow_live_gemini: bool = False
    allow_deterministic_fallback: bool = True
    founder_quality_threshold: float = Field(default=70, ge=0, le=100)
    sample_data: bool = False
    requested_at: datetime = Field(default_factory=utc_now)

    @field_validator("requested_at")
    @classmethod
    def aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("requested_at must be timezone-aware.")
        return value


class MissionSummary(AuraBaseModel):
    mission_id: UUID
    title: str
    current_state: MissionExecutionStatus
    founder_approval: str
    assigned_employees: list[str]
    artifact_count: int = Field(ge=0)
    progress_percentage: float = Field(ge=0, le=100)
    artifacts: list["ArtifactVersionSummary"] = Field(default_factory=list)


class ArtifactVersionSummary(AuraBaseModel):
    artifact_id: UUID
    artifact_type: str
    name: str
    version_number: int = Field(ge=1)
    status: str


class ThumbnailReviewPackage(AuraBaseModel):
    headline: str
    visual_direction: str
    review_notes: list[str] = Field(default_factory=list)


class ShortFormReviewPackage(AuraBaseModel):
    clip_count: int = Field(ge=0)
    hooks: list[str] = Field(default_factory=list)


class MetadataReviewPackage(AuraBaseModel):
    title: str
    description_guidance: str
    keywords: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list)
    cross_platform_captions: dict[ContentPlatform, str] = Field(
        default_factory=dict
    )
    evidence_classification: EvidenceClassification


class ProductionReviewPackage(AuraBaseModel):
    package_id: UUID
    script_versions: int = Field(ge=1)
    quality_score: float = Field(ge=0, le=100)
    blocking_issues: list[str] = Field(default_factory=list)
    rendered: bool = False
    published: bool = False

    @model_validator(mode="after")
    def no_delivery_side_effects(self) -> "ProductionReviewPackage":
        if self.rendered or self.published:
            raise ValueError("Review packages cannot be rendered or published.")
        return self


class FounderReviewPackage(AuraBaseModel):
    mission_objective: str
    target_audience: str
    research_summary: str
    evidence_limitations: list[str] = Field(default_factory=list)
    primary_keyword: str
    title_options: list[str] = Field(default_factory=list)
    recommended_title: str
    script_hook: str
    section_list: list[str] = Field(default_factory=list)
    word_count: int = Field(ge=0)
    estimated_duration_seconds: float = Field(ge=0)
    verification_warnings: list[str] = Field(default_factory=list)
    quality_score: float = Field(ge=0, le=100)
    gate_status: str
    revision_history: list[str] = Field(default_factory=list)
    blocking_issues: list[str] = Field(default_factory=list)
    founder_decisions_required: list[str] = Field(default_factory=list)
    provider_review_recommendations: list[str] = Field(default_factory=list)
    rendered: bool = False
    published: bool = False


class ProviderStageSummary(AuraBaseModel):
    capability: ProviderCapability
    provider: str = Field(min_length=1, max_length=100)
    fallback_used: bool
    request_count: int = Field(ge=0, le=1)


class ProviderUsageSummary(AuraBaseModel):
    live_enabled: bool = False
    total_requests: int = Field(default=0, ge=0)
    fallback_used: bool = True
    stages: list[ProviderStageSummary] = Field(default_factory=list)


class FirstContentMissionResult(AuraBaseModel):
    mission_summary: MissionSummary
    mission: Mission
    pilot: RealContentPilotResult
    production_package: ProductionPackage
    creative_quality_package: CreativeQualityPackage
    script_versions: list[ScriptArtifact] = Field(min_length=1)
    founder_review: FounderReviewPackage
    thumbnail_review: ThumbnailReviewPackage
    short_form_review: ShortFormReviewPackage
    metadata_review: MetadataReviewPackage
    production_review: ProductionReviewPackage
    provider_usage: ProviderUsageSummary
    evidence_register: list[EvidenceItem] = Field(default_factory=list)
    export_status: str = "not_exported"
    exported_path: str | None = None
    generated_at: datetime = Field(default_factory=utc_now)

    def dashboard_projection(self) -> dict[str, object]:
        """Return safe summaries without full scripts or provider payloads."""

        return self.model_dump(
            mode="json",
            exclude={
                "mission",
                "pilot",
                "production_package",
                "creative_quality_package",
                "script_versions",
            },
        )
