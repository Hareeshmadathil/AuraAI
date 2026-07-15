"""Typed models for deterministic AI production-provider research."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import Field, HttpUrl, field_validator

from core import AuraBaseModel, utc_now


class ProviderCategory(StrEnum):
    """Production capabilities evaluated by the department."""

    VOICE = "voice"
    AI_AVATAR = "ai_avatar"
    VIDEO_GENERATOR = "video_generator"
    THUMBNAIL_GENERATOR = "thumbnail_generator"
    IMAGE_MODEL = "image_model"
    SCRIPT_MODEL = "script_model"
    RESEARCH_MODEL = "research_model"


class ProviderStatus(StrEnum):
    """Founder-controlled provider recommendation status."""

    CANDIDATE = "candidate"
    APPROVED = "approved"
    DEPRECATED = "deprecated"


class PricingModel(StrEnum):
    """Coarse pricing structure recorded without volatile price claims."""

    FREE = "free"
    FREEMIUM = "freemium"
    SUBSCRIPTION = "subscription"
    USAGE_BASED = "usage_based"
    HYBRID = "hybrid"
    LOCAL_LICENSE = "local_license"
    UNKNOWN = "unknown"


class ProviderRecord(AuraBaseModel):
    """One manually maintained, locally scored provider candidate."""

    name: str = Field(min_length=1, max_length=200)
    category: ProviderCategory
    website: HttpUrl
    free_tier_available: bool
    trial_available: bool
    api_available: bool
    commercial_license_notes: str = Field(min_length=1, max_length=2000)
    pricing_model: PricingModel
    strengths: list[str] = Field(min_length=1, max_length=12)
    weaknesses: list[str] = Field(min_length=1, max_length=12)
    recommended_use_case: str = Field(min_length=1, max_length=1000)
    local_score: int = Field(ge=0, le=100)
    last_reviewed: date
    status: ProviderStatus = ProviderStatus.CANDIDATE
    placeholder_data: bool = True

    @field_validator("strengths", "weaknesses")
    @classmethod
    def validate_distinct_notes(cls, values: list[str]) -> list[str]:
        """Reject empty or duplicate evaluation notes."""

        normalized = [value.strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError("Provider evaluation notes cannot be empty.")
        if len({value.casefold() for value in normalized}) != len(normalized):
            raise ValueError("Provider evaluation notes must be distinct.")
        return normalized


class ProviderCategorySummary(AuraBaseModel):
    """Aggregate research state for one production capability."""

    category: ProviderCategory
    provider_count: int = Field(ge=0)
    approved_count: int = Field(ge=0)
    average_score: float = Field(ge=0, le=100)
    recommended_provider: str | None = None


class ProviderResearchReport(AuraBaseModel):
    """Deterministic snapshot of the manually curated research catalog."""

    department_name: str = "AI Production Research"
    generated_at: datetime = Field(default_factory=utc_now)
    methodology: str = Field(min_length=1, max_length=2000)
    data_notice: str = Field(min_length=1, max_length=1000)
    categories: list[ProviderCategorySummary]
    providers: list[ProviderRecord]
    network_requests_performed: bool = False

    @field_validator("network_requests_performed")
    @classmethod
    def prohibit_network_research(cls, value: bool) -> bool:
        if value:
            raise ValueError("Production research must remain offline.")
        return value
