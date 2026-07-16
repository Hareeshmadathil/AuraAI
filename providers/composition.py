"""Explicit provider composition root with deterministic defaults."""

from __future__ import annotations

from typing import TYPE_CHECKING

from providers.cache import MemoryProviderCache
from providers.deterministic_provider import DeterministicProvider
from providers.gemini.config import GeminiConfig
from providers.gemini.provider import GeminiProvider
from providers.gemini.transport import GeminiTransport, UnavailableGeminiTransport
from providers.multi_llm import ProviderRoutingMode
from providers.nemotron.config import NemotronConfig
from providers.nemotron.provider import NemotronProvider
from providers.nemotron.transport import NemotronTransport, UnavailableNemotronTransport
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
    nemotron_config: NemotronConfig | None = None,
    nemotron_transport: NemotronTransport | None = None,
    routing_mode: ProviderRoutingMode = ProviderRoutingMode.AUTO,
    default_provider: str | None = None,
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
    if nemotron_config is not None:
        registry.register_provider(NemotronProvider(nemotron_config, nemotron_transport or UnavailableNemotronTransport()))
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
        routing_mode=routing_mode,
        default_provider=default_provider,
    )


def create_multi_llm_router(
    settings: "MultiLLMSettings | None" = None,
    *,
    gemini_transport: GeminiTransport | None = None,
    nemotron_transport: NemotronTransport | None = None,
    event_bus: RuntimeEventBus | None = None,
) -> ProviderRouter:
    """Compose both text providers from environment-derived settings."""
    from providers.settings import MultiLLMSettings

    selected=settings or MultiLLMSettings.from_environment()
    return create_provider_router(selected.gemini, gemini_transport,
        event_bus=event_bus, nemotron_config=selected.nemotron,
        nemotron_transport=nemotron_transport, routing_mode=selected.mode,
        default_provider=selected.default_provider)
