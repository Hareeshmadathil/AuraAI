"""Typed, versioned outputs for the Real Content Pilot."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import ConfigDict, Field, field_validator, model_validator

from core import AuraBaseModel, utc_now
from creative_quality.models import QualityGateStatus


class FounderReviewStatus(StrEnum):
    """Explicit founder disposition for a review package."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISION_REQUESTED = "revision_requested"


class _ImmutableArtifact(AuraBaseModel):
    """Shared immutable metadata for pilot artifacts."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        use_enum_values=False,
    )
    artifact_id: UUID = Field(default_factory=uuid4)
    mission_id: UUID
    version_number: int = Field(default=1, ge=1)
    parent_artifact_id: UUID | None = None
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at")
    @classmethod
    def timestamp_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Artifact timestamps must be timezone-aware.")
        return value

class ResearchArtifact(_ImmutableArtifact):
    topic: str = Field(min_length=1)
    executive_summary: str = Field(min_length=1)
    audience_needs: list[str] = Field(min_length=1)
    key_questions: list[str] = Field(min_length=1)
    evidence_summary: list[str] = Field(default_factory=list)
    supplied_sources: list[str] = Field(default_factory=list)
    verification_required: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    provider_used: str = Field(min_length=1, max_length=100)
    fallback_used: bool


class SEOArtifact(_ImmutableArtifact):
    primary_keyword: str = Field(min_length=1)
    secondary_keywords: list[str] = Field(default_factory=list)
    search_intent: str = Field(min_length=1)
    title_options: list[str] = Field(min_length=1)
    description_outline: list[str] = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list)
    chapter_keywords: list[str] = Field(default_factory=list)
    difficulty_notes: list[str] = Field(default_factory=list)
    verification_required: list[str] = Field(default_factory=list)
    provider_used: str = Field(min_length=1, max_length=100)
    fallback_used: bool


class ScriptArtifact(_ImmutableArtifact):
    title: str = Field(min_length=1)
    hook: str = Field(min_length=1)
    sections: list[str] = Field(min_length=1)
    call_to_action: str = Field(min_length=1)
    word_count: int = Field(ge=1)
    estimated_duration_seconds: float = Field(gt=0)
    claims_requiring_verification: list[str] = Field(default_factory=list)
    source_notes: list[str] = Field(default_factory=list)
    provider_used: str = Field(min_length=1, max_length=100)
    fallback_used: bool


class CreativeQualityArtifact(_ImmutableArtifact):
    quality_package_id: UUID
    overall_score: float = Field(ge=0, le=100)
    gate_status: QualityGateStatus
    blocking_issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    revision_count: int = Field(ge=0, le=1)
    founder_override_allowed: bool


class ProductionPackageArtifact(_ImmutableArtifact):
    """Version metadata for a review-only structured production package."""

    production_package_id: UUID
    script_id: UUID
    approval_status: str = Field(min_length=1)
    render_status: str = Field(min_length=1)
    rendered: bool = False
    published: bool = False

    @model_validator(mode="after")
    def preserve_delivery_gate(self) -> "ProductionPackageArtifact":
        if self.rendered or self.published:
            raise ValueError("Revision packages cannot be rendered or published.")
        return self


class RevisionRequestArtifact(_ImmutableArtifact):
    """Immutable founder instruction for one bounded content revision."""

    notes: str = Field(min_length=1, max_length=10_000)
    objectives: list[str] = Field(min_length=1)
    requested_by: str = Field(default="Founder", min_length=1)


class FounderReviewArtifact(_ImmutableArtifact):
    review_status: FounderReviewStatus = FounderReviewStatus.PENDING
    research_summary: str = Field(min_length=1)
    seo_summary: str = Field(min_length=1)
    script_summary: str = Field(min_length=1)
    quality_summary: str = Field(min_length=1)
    blocking_items: list[str] = Field(default_factory=list)
    recommended_action: str = Field(min_length=1)
    founder_notes: str | None = None
    reviewed_at: datetime | None = None

    @field_validator("reviewed_at")
    @classmethod
    def reviewed_timestamp_is_aware(
        cls, value: datetime | None
    ) -> datetime | None:
        if value is not None and (
            value.tzinfo is None or value.utcoffset() is None
        ):
            raise ValueError("reviewed_at must be timezone-aware.")
        return value
