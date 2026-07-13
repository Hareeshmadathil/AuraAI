"""Runtime event and state integration for provider routing."""

from providers import (
    DeterministicProvider,
    PromptCategory,
    ProviderCapability,
    ProviderRegistry,
    ProviderRouter,
    build_department_prompt,
)
from runtime_engine import RuntimeEventBus, RuntimeStateManager
from runtime_engine.models import RuntimeEventType


def test_router_emits_provider_events_and_updates_runtime_state() -> None:
    bus = RuntimeEventBus()
    registry = ProviderRegistry()
    registry.register_provider(DeterministicProvider())
    router = ProviderRouter(registry, event_bus=bus)
    router.route(
        ProviderCapability.SEO,
        build_department_prompt(
            "runtime_seo",
            PromptCategory.STRATEGY,
            "responsible AI education",
        ),
    )
    state = RuntimeStateManager(bus)
    state.update_provider_state(router.build_state())
    snapshot = state.snapshot()

    assert snapshot.statistics.provider_requests == 1
    assert snapshot.provider_state.usage[0].capability == ProviderCapability.SEO
    assert bus.filter_by_type(RuntimeEventType.PROVIDER_SELECTED)
    assert bus.filter_by_type(RuntimeEventType.PROVIDER_COMPLETED)


def test_missing_provider_emits_fallback_event() -> None:
    bus = RuntimeEventBus()
    router = ProviderRouter(ProviderRegistry(), event_bus=bus)
    result = router.route(
        ProviderCapability.STORY,
        build_department_prompt(
            "runtime_story",
            PromptCategory.CREATION,
            "a truthful case study",
        ),
    )

    assert result.fallback_used is True
    assert bus.filter_by_type(RuntimeEventType.PROVIDER_FAILED)
    assert bus.filter_by_type(RuntimeEventType.PROVIDER_FALLBACK)
