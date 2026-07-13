"""Core AI provider registry, router, prompts, validation, and cache tests."""

import pytest

from providers import (
    DeterministicProvider,
    MemoryProviderCache,
    PromptCategory,
    PromptTemplate,
    PromptVariable,
    ProviderCapability,
    ProviderRateLimiter,
    ProviderRegistry,
    ProviderRouter,
    ProviderUsageTracker,
    ResearchOutput,
    ResponseValidator,
    SafetyValidator,
)
from providers.exceptions import ProviderRateLimitError, ProviderValidationError
from providers.gemini import (
    GeminiConfig,
    GeminiProvider,
    GeminiResponseParser,
)


def build_prompt(subject: str = "responsible creator workflows"):
    template = PromptTemplate(
        name="provider_test",
        template="Analyze {subject}",
        category=PromptCategory.RESEARCH,
    )
    return template.render([PromptVariable(name="subject", value=subject)])


def test_registry_resolves_registered_capability() -> None:
    registry = ProviderRegistry()
    provider = DeterministicProvider()
    registry.register_provider(provider)

    assert registry.resolve(ProviderCapability.SCRIPT) is provider
    assert registry.descriptors() == (provider.descriptor,)


def test_router_returns_typed_output_and_tracks_usage() -> None:
    registry = ProviderRegistry()
    registry.register_provider(DeterministicProvider())
    tracker = ProviderUsageTracker()
    router = ProviderRouter(registry, usage_tracker=tracker)

    result = router.route(ProviderCapability.RESEARCH, build_prompt())

    assert isinstance(result.output, ResearchOutput)
    assert result.fallback_used is False
    assert tracker.total_requests() == 1
    assert result.usage.estimated_cost == 0


def test_disabled_gemini_stub_falls_back_without_network() -> None:
    registry = ProviderRegistry()
    registry.register_provider(GeminiProvider(GeminiConfig(enabled=True)))
    router = ProviderRouter(registry)

    result = router.route(ProviderCapability.SCRIPT, build_prompt())

    assert result.provider == "deterministic"
    assert result.fallback_used is True
    assert router.build_state().fallback_requests == 1


def test_memory_cache_is_optional_and_deterministic() -> None:
    registry = ProviderRegistry()
    registry.register_provider(DeterministicProvider())
    cache = MemoryProviderCache()
    router = ProviderRouter(registry, cache=cache)

    first = router.route(ProviderCapability.RESEARCH, build_prompt())
    second = router.route(ProviderCapability.RESEARCH, build_prompt())

    assert cache.size() == 1
    assert first.request_id == second.request_id
    assert router.usage_tracker.total_requests() == 1


def test_prompt_requires_exact_typed_variables() -> None:
    template = PromptTemplate(
        name="exact_variables",
        template="Review {subject}",
        category=PromptCategory.REVIEW,
    )

    with pytest.raises(ValueError, match="exactly match"):
        template.render([PromptVariable(name="topic", value="safe topic")])


def test_safety_rejects_credential_like_prompt() -> None:
    prompt = build_prompt("api_key='not-a-real-value'")

    with pytest.raises(ProviderValidationError, match="credential-like"):
        SafetyValidator().validate_prompt(prompt)


def test_response_validator_rejects_wrong_capability_model() -> None:
    result = DeterministicProvider().generate(
        ProviderCapability.RESEARCH,
        build_prompt(),
    )
    with pytest.raises(ProviderValidationError, match="different capability"):
        ResponseValidator().validate(ProviderCapability.SCRIPT, result)


def test_json_parser_requires_typed_object() -> None:
    parser = GeminiResponseParser()
    value = parser.parse(
        '{"findings":["Validate evidence"],"source_guidance":[]}',
        ResearchOutput,
    )
    assert value.findings == ["Validate evidence"]

    with pytest.raises(ProviderValidationError):
        parser.parse("not-json", ResearchOutput)


def test_rate_limit_fails_closed_without_sleeping() -> None:
    limiter = ProviderRateLimiter(maximum_requests=1)
    limiter.acquire("test")
    with pytest.raises(ProviderRateLimitError):
        limiter.acquire("test")


def test_gemini_config_credential_field_is_explicit_and_excluded() -> None:
    assert "api_key" in GeminiConfig.model_fields
    assert GeminiConfig.model_fields["api_key"].exclude is True
    assert "credentials" not in GeminiConfig.model_fields
