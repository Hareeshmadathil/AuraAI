"""Safe provider selection, validation, fallback, cache, and usage routing."""

from __future__ import annotations

from time import perf_counter
from typing import TYPE_CHECKING

from core import get_logger
from providers.base import Provider
from providers.cache import MemoryProviderCache, provider_cache_key
from providers.deterministic_provider import DeterministicProvider
from providers.models import (
    ProviderCapability,
    ProviderHealth,
    ProviderOutput,
    ProviderState,
)
from providers.prompt_template import ProviderPrompt
from providers.provider_result import ProviderResult
from providers.rate_limits import ProviderRateLimiter
from providers.registry import ProviderRegistry
from providers.safety import ResponseValidator, SafetyValidator
from providers.usage import ProviderUsageTracker

if TYPE_CHECKING:
    from runtime_engine.event_bus import RuntimeEventBus


class ProviderRouter:
    """Resolve providers without exposing vendor identity to employees."""

    def __init__(
        self,
        registry: ProviderRegistry,
        *,
        fallback: Provider | None = None,
        cache: MemoryProviderCache | None = None,
        usage_tracker: ProviderUsageTracker | None = None,
        rate_limiter: ProviderRateLimiter | None = None,
        event_bus: RuntimeEventBus | None = None,
        safety_validator: SafetyValidator | None = None,
        response_validator: ResponseValidator | None = None,
    ) -> None:
        self.registry = registry
        self.fallback = fallback or DeterministicProvider()
        self.cache = cache
        self.usage_tracker = usage_tracker or ProviderUsageTracker()
        self.rate_limiter = rate_limiter or ProviderRateLimiter()
        self.event_bus = event_bus
        self.safety_validator = safety_validator or SafetyValidator()
        self.response_validator = response_validator or ResponseValidator()
        self.logger = get_logger("providers.router")

    def route(
        self,
        capability: ProviderCapability,
        prompt: ProviderPrompt,
    ) -> ProviderResult[ProviderOutput]:
        """Return validated typed output, falling back on every provider failure."""

        self.safety_validator.validate_prompt(prompt)
        cache_key = provider_cache_key(capability, prompt)
        if self.cache is not None:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return ProviderResult[ProviderOutput].model_validate(cached)

        try:
            provider = self.registry.resolve(capability)
            self._emit(
                "PROVIDER_SELECTED",
                f"Provider selected for {capability.value}.",
                provider.descriptor.name,
            )
            result = self._call(provider, capability, prompt, fallback_used=False)
        except Exception as error:
            self.logger.warning(
                "Provider failed for capability %s; deterministic fallback selected (%s).",
                capability.value,
                error.__class__.__name__,
            )
            self._emit(
                "PROVIDER_FAILED",
                f"Provider failed for {capability.value}; no prompt data retained.",
            )
            self._emit(
                "PROVIDER_FALLBACK",
                f"Deterministic fallback selected for {capability.value}.",
                self.fallback.descriptor.name,
            )
            result = self._call(self.fallback, capability, prompt, fallback_used=True)

        if self.cache is not None:
            self.cache.set(cache_key, result)
        self._emit(
            "PROVIDER_COMPLETED",
            f"Provider completed {capability.value}.",
            result.provider,
        )
        return result

    def build_state(self) -> ProviderState:
        """Project safe registry and metadata state for runtime/dashboard use."""

        descriptors = list(self.registry.descriptors())
        fallback_descriptor = self.fallback.descriptor
        if all(item.name != fallback_descriptor.name for item in descriptors):
            descriptors.append(fallback_descriptor)
        usage = list(self.usage_tracker.list_usage())
        return ProviderState(
            providers=descriptors,
            health=[
                ProviderHealth(
                    name=item.name,
                    enabled=item.enabled,
                    status=(
                        "disabled"
                        if not item.enabled
                        else "placeholder"
                        if item.kind.value == "stub"
                        else "available"
                    ),
                    capabilities=sorted(item.capabilities, key=lambda value: value.value),
                    fallback=item.name == fallback_descriptor.name,
                )
                for item in descriptors
            ],
            usage=usage,
            cache_entries=self.cache.size() if self.cache is not None else 0,
            fallback_requests=sum(item.fallback_used for item in usage),
        )

    def _call(
        self,
        provider: Provider,
        capability: ProviderCapability,
        prompt: ProviderPrompt,
        *,
        fallback_used: bool,
    ) -> ProviderResult[ProviderOutput]:
        self.rate_limiter.acquire(provider.descriptor.name)
        started = perf_counter()
        result = provider.generate(capability, prompt)
        result.fallback_used = fallback_used
        result.usage.fallback_used = fallback_used
        result.usage.latency_ms = max(
            result.usage.latency_ms,
            (perf_counter() - started) * 1000,
        )
        self.response_validator.validate(capability, result)
        self.safety_validator.validate_response(result.output)
        self.usage_tracker.record(result.usage)
        return result

    def _emit(self, event_name: str, message: str, provider: str | None = None) -> None:
        if self.event_bus is None:
            return
        from runtime_engine.models import RuntimeEventType

        self.event_bus.emit(
            RuntimeEventType[event_name],
            message,
            metadata={"provider": provider} if provider else {},
        )
