"""Founder-supplied input for the Real Content Pilot."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator

from core import AuraBaseModel, ContentPlatform, utc_now
from production.models import VideoStyle


class RealContentPilotInput(AuraBaseModel):
    """Validated, credential-free instructions for one content mission."""

    title: str = Field(min_length=1, max_length=250)
    objective: str = Field(min_length=1, max_length=5000)
    topic: str = Field(min_length=1, max_length=500)
    target_audience: str = Field(min_length=1, max_length=2000)
    audience_problem: str = Field(min_length=1, max_length=3000)
    audience_promise: str = Field(min_length=1, max_length=3000)
    primary_platform: ContentPlatform = ContentPlatform.YOUTUBE
    language: str = Field(min_length=1, max_length=100)
    tone: str = Field(min_length=1, max_length=500)
    target_duration_seconds: int = Field(ge=60, le=1800)
    content_goal: str = Field(min_length=1, max_length=3000)
    preferred_call_to_action: str | None = Field(default=None, max_length=1000)
    preferred_style: VideoStyle | None = None
    source_notes: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    primary_keyword: str | None = Field(default=None, max_length=250)
    secondary_keywords: list[str] = Field(default_factory=list)
    founder_requires_live_ai: bool = False
    allow_deterministic_fallback: bool = True
    sample_data: bool = False
    requested_at: datetime = Field(default_factory=utc_now)

    @field_validator("requested_at")
    @classmethod
    def timestamp_is_aware(cls, value: datetime) -> datetime:
        """Require an unambiguous request timestamp."""

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("requested_at must be timezone-aware.")
        return value
