"""Live-mode authorization and deterministic fallback tests."""

import pytest
from pydantic import SecretStr

from company_missions.first_real_content.dashboard import create_sample_first_content_input
from company_missions.first_real_content.runner import FirstRealContentMissionRunner
from core import ValidationError
from providers import create_provider_router
from providers.gemini import GeminiConfig, MockGeminiTransport
from tests.gemini_helpers import response_for


def test_live_input_without_injected_approval_fails_when_fallback_disabled() -> None:
    value = create_sample_first_content_input().model_copy(
        update={"allow_live_gemini": True, "allow_deterministic_fallback": False}
    )
    with pytest.raises(ValidationError) as caught:
        FirstRealContentMissionRunner().run_typed(value)
    assert caught.value.error_code == "LIVE_AI_NOT_APPROVED"


def test_default_result_contains_no_vendor_transport_or_raw_response() -> None:
    result = FirstRealContentMissionRunner().run_typed(create_sample_first_content_input())
    serialized = result.model_dump_json().lower()
    assert "raw_response" not in serialized
    assert "api_key" not in serialized
    assert result.provider_usage.live_enabled is False


def test_mocked_live_mode_uses_six_bounded_capabilities() -> None:
    transport = MockGeminiTransport(lambda request: response_for(request))
    config = GeminiConfig(
        enabled=True,
        allow_live_requests=True,
        api_key=SecretStr("test-placeholder"),
        maximum_retries=0,
        request_budget=6,
    )
    value = create_sample_first_content_input().model_copy(
        update={"allow_live_gemini": True}
    )
    result = FirstRealContentMissionRunner(
        provider_router=create_provider_router(config, transport),
        founder_approved_live_ai=True,
    ).run_typed(value)

    assert result.provider_usage.total_requests == 6
    assert {item.capability.value for item in result.provider_usage.stages} == {
        "research", "seo", "script", "hook", "review", "metadata"
    }
    assert len(transport.requests) == 6
