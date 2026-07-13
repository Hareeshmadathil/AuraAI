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
        fallback_enabled: bool = True,
    ) -> None:
        self.registry = registry
        self.fallback = fallback or DeterministicProvider()
        self.cache = cache
        self.usage_tracker = usage_tracker or ProviderUsageTracker()
        self.rate_limiter = rate_limiter or ProviderRateLimiter()
        self.event_bus = event_bus
        self.safety_validator = safety_validator or SafetyValidator()
        self.response_validator = response_validator or ResponseValidator()
        self.fallback_enabled = fallback_enabled
        self._cache_hits = 0
        self._cache_hits_by_provider: dict[str, int] = {}
        self.logger = get_logger("providers.router")

    def route(
        self,
        capability: ProviderCapability,
        prompt: ProviderPrompt,
    ) -> ProviderResult[ProviderOutput]:
        """Return validated typed output, falling back on every provider failure."""

        self.safety_validator.validate_prompt(prompt)
        provider: Provider | None = None
        try:
            provider = self.registry.resolve(capability)
            self._check_ready(provider)
            self._emit(
                "PROVIDER_SELECTED",
                f"Provider selected for {capability.value}.",
                provider.descriptor.name,
            )
            self.rate_limiter.acquire(provider.descriptor.name)
            cache_key = provider_cache_key(
                capability,
                prompt,
                provider.descriptor.name,
            )
            cached = self._cached(cache_key, provider.descriptor.name)
            if cached is not None:
                return cached
            result = self._call(
                provider,
                capability,
                prompt,
                fallback_used=False,
                acquire_rate=False,
            )
        except Exception as error:
            self.logger.warning(
                "Provider failed for capability %s; deterministic fallback selected (%s).",
                capability.value,
                error.__class__.__name__,
            )
            safe_error_code = self._safe_error_code(error)
            self._emit(
                "PROVIDER_FAILED",
                f"Provider failed for {capability.value}; no prompt data retained.",
                provider.descriptor.name if provider is not None else None,
                safe_error_code=safe_error_code,
            )
            if provider is not None:
                recorder = getattr(provider, "record_fallback", None)
                if callable(recorder):
                    recorder(safe_error_code)
            if not self.fallback_enabled:
                raise
            self._emit(
                "PROVIDER_FALLBACK",
                f"Deterministic fallback selected for {capability.value}.",
                self.fallback.descriptor.name,
            )
            fallback_key = provider_cache_key(
                capability,
                prompt,
                self.fallback.descriptor.name,
            )
            cached = self._cached(
                fallback_key,
                self.fallback.descriptor.name,
            )
            if cached is not None:
                cached.fallback_used = True
                cached.usage.fallback_used = True
                return cached
            result = self._call(
                self.fallback,
                capability,
                prompt,
                fallback_used=True,
            )
            cache_key = fallback_key

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

        registered = list(self.registry.providers())
        descriptors = [provider.descriptor for provider in registered]
        fallback_descriptor = self.fallback.descriptor
        if all(item.name != fallback_descriptor.name for item in descriptors):
            descriptors.append(fallback_descriptor)
        usage = list(self.usage_tracker.list_usage())
        health: list[ProviderHealth] = []
        providers_by_name = {
            provider.descriptor.name: provider for provider in registered
        }
        for item in descriptors:
            provider = providers_by_name.get(item.name)
            health_builder = getattr(provider, "safe_health", None)
            if callable(health_builder):
                value = ProviderHealth.model_validate(health_builder())
            else:
                value = ProviderHealth(
                    name=item.name,
                    enabled=item.enabled,
                    status="available" if item.enabled else "disabled",
                    capabilities=sorted(
                        item.capabilities,
                        key=lambda capability: capability.value,
                    ),
                    fallback=item.name == fallback_descriptor.name,
                    model=item.model,
                )
            value.fallback = item.name == fallback_descriptor.name
            value.cache_hit_count = self._cache_hits_by_provider.get(item.name, 0)
            health.append(value)
        return ProviderState(
            providers=descriptors,
            health=health,
            usage=usage,
            cache_entries=self.cache.size() if self.cache is not None else 0,
            fallback_requests=sum(item.fallback_used for item in usage),
            cache_hits=self._cache_hits,
        )

    def _call(
        self,
        provider: Provider,
        capability: ProviderCapability,
        prompt: ProviderPrompt,
        *,
        fallback_used: bool,
        acquire_rate: bool = True,
    ) -> ProviderResult[ProviderOutput]:
        if acquire_rate:
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

    @staticmethod
    def _check_ready(provider: Provider) -> None:
        checker = getattr(provider, "check_ready", None)
        if callable(checker):
            checker()

    def _cached(
        self,
        cache_key: str,
        provider_name: str,
    ) -> ProviderResult[ProviderOutput] | None:
        if self.cache is None:
            return None
        cached = self.cache.get(cache_key)
        if cached is None:
            return None
        self._cache_hits += 1
        self._cache_hits_by_provider[provider_name] = (
            self._cache_hits_by_provider.get(provider_name, 0) + 1
        )
        value = ProviderResult[ProviderOutput].model_validate(cached)
        value.usage.cache_hit = True
        return value

    @staticmethod
    def _safe_error_code(error: Exception) -> str:
        return str(
            getattr(error, "details", {}).get("safe_error_code")
            or getattr(error, "error_code", error.__class__.__name__)
        )

    def _emit(
        self,
        event_name: str,
        message: str,
        provider: str | None = None,
        *,
        safe_error_code: str | None = None,
    ) -> None:
        if self.event_bus is None:
            return
        from runtime_engine.models import RuntimeEventType

        self.event_bus.emit(
            RuntimeEventType[event_name],
            message,
            metadata={
                **({"provider": provider} if provider else {}),
                **(
                    {"safe_error_code": safe_error_code}
                    if safe_error_code
                    else {}
                ),
            },
        )
