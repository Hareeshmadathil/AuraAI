"""Vendor-neutral provider contracts used by AuraAI employees."""

from __future__ import annotations

from typing import Protocol

from providers.models import (
    AnalyticsAdviceOutput, AnimationOutput, AudienceOutput, HookOutput,
    ImagePromptOutput, MarketingOutput, MetadataOutput, ProviderCapability,
    ProviderDescriptor, ProviderOutput, ResearchOutput, ReviewOutput,
    SEOOutput, SceneOutput, ScriptOutput, StoryOutput, VideoPromptOutput,
    FlowOutput,
)
from providers.prompt_template import ProviderPrompt
from providers.provider_result import ProviderResult


class Provider(Protocol):
    descriptor: ProviderDescriptor

    def generate(
        self, capability: ProviderCapability, prompt: ProviderPrompt
    ) -> ProviderResult[ProviderOutput]: ...


class ResearchProvider(Protocol):
    def research(self, prompt: ProviderPrompt) -> ProviderResult[ResearchOutput]: ...


class ScriptProvider(Protocol):
    def generate_script(self, prompt: ProviderPrompt) -> ProviderResult[ScriptOutput]: ...


class HookProvider(Protocol):
    def generate_hook(self, prompt: ProviderPrompt) -> ProviderResult[HookOutput]: ...


class StoryProvider(Protocol):
    def generate_story(self, prompt: ProviderPrompt) -> ProviderResult[StoryOutput]: ...


class SEOProvider(Protocol):
    def generate_seo(self, prompt: ProviderPrompt) -> ProviderResult[SEOOutput]: ...


class MarketingProvider(Protocol):
    def generate_marketing(
        self, prompt: ProviderPrompt
    ) -> ProviderResult[MarketingOutput]: ...


class ReviewProvider(Protocol):
    def review(self, prompt: ProviderPrompt) -> ProviderResult[ReviewOutput]: ...


class ImagePromptProvider(Protocol):
    def generate_image_prompt(
        self, prompt: ProviderPrompt
    ) -> ProviderResult[ImagePromptOutput]: ...


class VideoPromptProvider(Protocol):
    def generate_video_prompt(
        self, prompt: ProviderPrompt
    ) -> ProviderResult[VideoPromptOutput]: ...


class MetadataProvider(Protocol):
    def generate_metadata(
        self, prompt: ProviderPrompt
    ) -> ProviderResult[MetadataOutput]: ...


class AudienceProvider(Protocol):
    def analyze_audience(
        self, prompt: ProviderPrompt
    ) -> ProviderResult[AudienceOutput]: ...


class AnalyticsAdvisor(Protocol):
    def advise(
        self, prompt: ProviderPrompt
    ) -> ProviderResult[AnalyticsAdviceOutput]: ...


class SceneProvider(Protocol):
    def generate_scenes(
        self, prompt: ProviderPrompt
    ) -> ProviderResult[SceneOutput]: ...


class AnimationProvider(Protocol):
    def generate_animation(
        self, prompt: ProviderPrompt
    ) -> ProviderResult[AnimationOutput]: ...


class FlowProvider(Protocol):
    """Placeholder interface only; no Google Flow implementation exists."""

    def create_flow_plan(
        self, prompt: ProviderPrompt
    ) -> ProviderResult[FlowOutput]: ...
