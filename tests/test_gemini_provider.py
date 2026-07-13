"""Gemini capability, retry, fallback, cache, and usage tests."""

import pytest
from pydantic import SecretStr

from providers import (
    ProviderCapability,
    create_provider_router,
)
from providers.exceptions import ProviderTimeoutError
from providers.gemini import (
    GeminiConfig,
    GeminiProvider,
    GeminiTransportResponse,
    MockGeminiTransport,
)
from tests.gemini_helpers import prompt_for, response_for


def live_config(**changes) -> GeminiConfig:
    values = {
        "enabled": True,
        "allow_live_requests": True,
        "api_key": SecretStr("fake-provider-key"),
        "maximum_retries": 0,
    }
    values.update(changes)
    return GeminiConfig(**values)


@pytest.mark.parametrize(
    "capability",
    [
        ProviderCapability.RESEARCH,
        ProviderCapability.SCRIPT,
        ProviderCapability.HOOK,
        ProviderCapability.STORY,
        ProviderCapability.SEO,
        ProviderCapability.MARKETING,
        ProviderCapability.REVIEW,
        ProviderCapability.METADATA,
        ProviderCapability.AUDIENCE,
    ],
)
def test_all_v1_capabilities_return_neutral_typed_outputs(capability) -> None:
    transport = MockGeminiTransport(lambda request: response_for(request))
    provider = GeminiProvider(live_config(), transport)
    result = provider.generate(capability, prompt_for(capability))

    assert result.provider == "gemini"
    assert result.output.__class__.__module__ == "providers.models"
    assert result.usage.input_tokens == 12
    assert result.usage.output_tokens == 8
    assert len(transport.requests) == 1


def test_disabled_default_router_uses_deterministic_fallback() -> None:
    router = create_provider_router()
    result = router.route(
        ProviderCapability.RESEARCH,
        prompt_for(ProviderCapability.RESEARCH),
    )
    assert result.provider == "deterministic"
    assert result.fallback_used is True


def test_configured_router_selects_gemini_and_records_usage() -> None:
    transport = MockGeminiTransport(lambda request: response_for(request))
    router = create_provider_router(live_config(), transport)
    result = router.route(
        ProviderCapability.SEO,
        prompt_for(ProviderCapability.SEO),
    )
    state = router.build_state()
    gemini = next(item for item in state.health if item.name == "gemini")

    assert result.provider == "gemini"
    assert state.usage[0].prompt_hash
    assert gemini.request_count == 1
    assert gemini.success_count == 1
    assert gemini.input_tokens == 12


def test_timeout_and_invalid_response_fall_back_safely() -> None:
    def timeout(_request):
        raise ProviderTimeoutError(
            "mock timeout", provider_name="gemini", retryable=True
        )

    timeout_router = create_provider_router(
        live_config(maximum_retries=1),
        MockGeminiTransport(timeout),
    )
    timeout_result = timeout_router.route(
        ProviderCapability.HOOK,
        prompt_for(ProviderCapability.HOOK),
    )
    assert timeout_result.provider == "deterministic"
    assert timeout_result.fallback_used is True

    invalid_transport = MockGeminiTransport(
        lambda request: GeminiTransportResponse(
            request_id=request.request_id,
            status_code=200,
            response_body='{"candidates":[]}',
            latency_ms=1,
        )
    )
    invalid_router = create_provider_router(live_config(), invalid_transport)
    invalid_result = invalid_router.route(
        ProviderCapability.STORY,
        prompt_for(ProviderCapability.STORY),
    )
    assert invalid_result.provider == "deterministic"


def test_cache_hit_avoids_second_transport_request() -> None:
    transport = MockGeminiTransport(lambda request: response_for(request))
    router = create_provider_router(
        live_config(cache_enabled=True, request_budget=3),
        transport,
    )
    prompt = prompt_for(ProviderCapability.METADATA)
    first = router.route(ProviderCapability.METADATA, prompt)
    second = router.route(ProviderCapability.METADATA, prompt)

    assert first.request_id == second.request_id
    assert second.usage.cache_hit is True
    assert len(transport.requests) == 1
    assert router.build_state().cache_hits == 1


def test_request_budget_falls_back_before_transport() -> None:
    transport = MockGeminiTransport(lambda request: response_for(request))
    router = create_provider_router(
        live_config(request_budget=1),
        transport,
    )
    router.route(ProviderCapability.RESEARCH, prompt_for(ProviderCapability.RESEARCH))
    result = router.route(ProviderCapability.SEO, prompt_for(ProviderCapability.SEO))
    assert result.provider == "deterministic"
    assert len(transport.requests) == 1


def test_ai_review_advice_cannot_grant_approval() -> None:
    transport = MockGeminiTransport(lambda request: response_for(request))
    provider = GeminiProvider(live_config(), transport)
    result = provider.generate(
        ProviderCapability.REVIEW,
        prompt_for(ProviderCapability.REVIEW),
    )
    assert result.output.approved is False
    assert any("cannot grant" in warning for warning in result.warnings)


def test_authentication_failure_records_safe_code_then_falls_back() -> None:
    transport = MockGeminiTransport(
        lambda request: GeminiTransportResponse(
            request_id=request.request_id,
            status_code=401,
            response_body='{"error":"credential detail not retained"}',
            latency_ms=1,
        )
    )
    router = create_provider_router(live_config(), transport)
    result = router.route(
        ProviderCapability.RESEARCH,
        prompt_for(ProviderCapability.RESEARCH),
    )
    gemini = next(
        item for item in router.build_state().health if item.name == "gemini"
    )
    assert result.provider == "deterministic"
    assert gemini.failure_count == 1
    assert gemini.fallback_count == 1
    assert gemini.last_safe_error_code == "authentication_rejected"
