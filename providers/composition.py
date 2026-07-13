"""Explicit provider composition root with deterministic defaults."""

from __future__ import annotations

from typing import TYPE_CHECKING

from providers.cache import MemoryProviderCache
from providers.deterministic_provider import DeterministicProvider
from providers.gemini.config import GeminiConfig
from providers.gemini.provider import GeminiProvider
from providers.gemini.transport import GeminiTransport, UnavailableGeminiTransport
from providers.rate_limits import ProviderRateLimiter
from providers.registry import ProviderRegistry
from providers.router import ProviderRouter

if TYPE_CHECKING:
    from runtime_engine.event_bus import RuntimeEventBus


def create_provider_router(
    config: GeminiConfig | None = None,
    transport: GeminiTransport | None = None,
    *,
    event_bus: RuntimeEventBus | None = None,
) -> ProviderRouter:
    """Compose an isolated router without reading credentials or networking."""

    selected_config = config or GeminiConfig()
    registry = ProviderRegistry()
    registry.register_provider(
        GeminiProvider(
            selected_config,
            transport or UnavailableGeminiTransport(),
        )
    )
    maximum_requests = (
        selected_config.request_budget
        or selected_config.daily_request_limit
        or 1000
    )
    return ProviderRouter(
        registry,
        fallback=DeterministicProvider(),
        cache=MemoryProviderCache() if selected_config.cache_enabled else None,
        rate_limiter=ProviderRateLimiter(maximum_requests),
        event_bus=event_bus,
        fallback_enabled=selected_config.fallback_enabled,
    )
