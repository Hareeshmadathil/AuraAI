"""Single public AI abstraction layer for AuraAI."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from providers.composition import create_provider_router

from providers.base import (
    AnalyticsAdvisor, AnimationProvider, AudienceProvider, FlowProvider,
    HookProvider, ImagePromptProvider, MarketingProvider, MetadataProvider,
    Provider, ResearchProvider, ReviewProvider, SceneProvider, ScriptProvider,
    SEOProvider, StoryProvider, VideoPromptProvider,
)
from providers.cache import MemoryProviderCache, provider_cache_key
from providers.deterministic_provider import DeterministicProvider
from providers.models import (
    AnalyticsAdviceOutput,
    AnimationOutput,
    AudienceOutput,
    FlowOutput,
    HookOutput,
    ImagePromptOutput,
    MarketingOutput,
    MetadataOutput,
    ProviderCapability,
    ProviderDescriptor,
    ProviderHealth,
    ProviderKind,
    ProviderOutput,
    ProviderState,
    ProviderUsage,
    ResearchOutput,
    ReviewOutput,
    SEOOutput,
    SceneOutput,
    ScriptOutput,
    StoryOutput,
    VideoPromptOutput,
)
from providers.prompt_template import (
    PromptCategory, PromptSafetyLevel, PromptTemplate, PromptVariable,
    ProviderPrompt, build_department_prompt,
)
from providers.provider_result import ProviderResult
from providers.rate_limits import ProviderRateLimiter
from providers.registry import ProviderRegistry
from providers.router import ProviderRouter
from providers.safety import ResponseValidator, SafetyValidator
from providers.usage import ProviderUsage, ProviderUsageTracker

__all__ = [
    "AnalyticsAdviceOutput", "AnalyticsAdvisor", "AnimationOutput",
    "AnimationProvider", "AudienceOutput", "AudienceProvider",
    "DeterministicProvider", "FlowProvider", "HookProvider",
    "FlowOutput", "HookOutput", "ImagePromptOutput", "ImagePromptProvider",
    "MarketingOutput", "MarketingProvider", "MemoryProviderCache",
    "MetadataOutput", "MetadataProvider", "PromptCategory", "PromptSafetyLevel",
    "PromptTemplate", "PromptVariable", "Provider", "ProviderPrompt",
    "ProviderCapability", "ProviderDescriptor", "ProviderHealth",
    "ProviderKind", "ProviderOutput", "ProviderRateLimiter",
    "ProviderRegistry", "ProviderResult", "ProviderRouter", "ProviderState",
    "ProviderUsage", "ProviderUsageTracker", "ResearchOutput",
    "ResearchProvider", "ResponseValidator", "ReviewOutput", "ReviewProvider",
    "SafetyValidator", "SceneOutput", "SceneProvider", "ScriptOutput",
    "ScriptProvider", "SEOOutput", "SEOProvider", "StoryOutput",
    "StoryProvider", "VideoPromptOutput", "VideoPromptProvider", "provider_cache_key",
    "build_department_prompt",
    "create_provider_router",
]


def __getattr__(name: str) -> Any:
    """Load the optional composition root without import-time coupling."""

    if name == "create_provider_router":
        from providers.composition import create_provider_router

        return create_provider_router
    raise AttributeError(name)
