"""Typed, provider-neutral request and response models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field

from core import AuraBaseModel, utc_now


class ProviderCapability(StrEnum):
    """AI capabilities routable without naming a vendor."""

    RESEARCH = "research"
    SCRIPT = "script"
    HOOK = "hook"
    STORY = "story"
    SEO = "seo"
    MARKETING = "marketing"
    REVIEW = "review"
    IMAGE_PROMPT = "image_prompt"
    VIDEO_PROMPT = "video_prompt"
    METADATA = "metadata"
    AUDIENCE = "audience"
    ANALYTICS = "analytics"
    SCENE = "scene"
    ANIMATION = "animation"
    FLOW = "flow"


class ProviderKind(StrEnum):
    """Provider implementation categories shown in runtime projections."""

    DETERMINISTIC = "deterministic"
    STUB = "stub"
    REMOTE = "remote"


class ProviderDescriptor(AuraBaseModel):
    """Safe provider identity with no configuration secrets."""

    name: str = Field(min_length=1, max_length=100)
    kind: ProviderKind
    enabled: bool = True
    model: str | None = Field(default=None, max_length=150)
    capabilities: frozenset[ProviderCapability] = Field(min_length=1)


class ResearchOutput(AuraBaseModel):
    findings: list[str] = Field(min_length=1)
    source_guidance: list[str] = Field(default_factory=list)


class ScriptOutput(AuraBaseModel):
    title: str = Field(min_length=1, max_length=250)
    sections: list[str] = Field(min_length=1)
    call_to_action: str = Field(min_length=1, max_length=500)


class HookOutput(AuraBaseModel):
    primary_hook: str = Field(min_length=1, max_length=500)
    alternatives: list[str] = Field(default_factory=list)


class StoryOutput(AuraBaseModel):
    narrative_arc: str = Field(min_length=1, max_length=1000)
    beats: list[str] = Field(min_length=1)


class SEOOutput(AuraBaseModel):
    primary_keyword: str = Field(min_length=1, max_length=250)
    secondary_keywords: list[str] = Field(default_factory=list)
    title_guidance: str = Field(min_length=1, max_length=1000)


class MarketingOutput(AuraBaseModel):
    positioning: str = Field(min_length=1, max_length=1000)
    content_pillars: list[str] = Field(min_length=1)
    campaign_goals: list[str] = Field(min_length=1)


class ReviewOutput(AuraBaseModel):
    approved: bool
    score: float = Field(ge=0, le=100)
    findings: list[str] = Field(default_factory=list)


class ImagePromptOutput(AuraBaseModel):
    prompt: str = Field(min_length=1, max_length=5000)
    exclusions: list[str] = Field(default_factory=list)


class VideoPromptOutput(AuraBaseModel):
    prompt: str = Field(min_length=1, max_length=5000)
    shot_guidance: list[str] = Field(default_factory=list)


class MetadataOutput(AuraBaseModel):
    title: str = Field(min_length=1, max_length=250)
    description: str = Field(min_length=1, max_length=5000)
    tags: list[str] = Field(default_factory=list)


class AudienceOutput(AuraBaseModel):
    persona_name: str = Field(min_length=1, max_length=150)
    needs: list[str] = Field(min_length=1)
    objections: list[str] = Field(default_factory=list)


class AnalyticsAdviceOutput(AuraBaseModel):
    observations: list[str] = Field(min_length=1)
    recommendations: list[str] = Field(min_length=1)


class SceneOutput(AuraBaseModel):
    scene_prompts: list[str] = Field(min_length=1)


class AnimationOutput(AuraBaseModel):
    motion_prompts: list[str] = Field(min_length=1)


class FlowOutput(AuraBaseModel):
    available: bool = False
    message: str = Field(min_length=1, max_length=1000)


ProviderOutput = (
    ResearchOutput
    | ScriptOutput
    | HookOutput
    | StoryOutput
    | SEOOutput
    | MarketingOutput
    | ReviewOutput
    | ImagePromptOutput
    | VideoPromptOutput
    | MetadataOutput
    | AudienceOutput
    | AnalyticsAdviceOutput
    | SceneOutput
    | AnimationOutput
    | FlowOutput
)


class ProviderHealth(AuraBaseModel):
    """One dashboard-safe provider health projection."""

    name: str
    enabled: bool
    status: str
    capabilities: list[ProviderCapability] = Field(default_factory=list)
    fallback: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class ProviderUsage(AuraBaseModel):
    """Metadata-only request usage with no prompt or response content."""

    request_id: UUID = Field(default_factory=uuid4)
    provider: str = Field(min_length=1, max_length=100)
    model: str | None = Field(default=None, max_length=150)
    capability: ProviderCapability
    tokens_requested: int = Field(default=0, ge=0)
    estimated_cost: float = Field(default=0.0, ge=0)
    latency_ms: float = Field(default=0.0, ge=0)
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime = Field(default_factory=utc_now)
    fallback_used: bool = False
    succeeded: bool = True


class ProviderState(AuraBaseModel):
    """Safe provider projection shared by runtime and dashboard."""

    providers: list[ProviderDescriptor] = Field(default_factory=list)
    health: list[ProviderHealth] = Field(default_factory=list)
    usage: list[ProviderUsage] = Field(default_factory=list)
    cache_entries: int = Field(default=0, ge=0)
    fallback_requests: int = Field(default=0, ge=0)
