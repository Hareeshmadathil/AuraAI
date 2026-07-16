"""Regression tests for safe Nemotron final-answer extraction."""
from __future__ import annotations

import json
from pydantic import BaseModel, ConfigDict, SecretStr, ValidationError
import pytest

from providers import ProviderCapability, ProviderRoutingMode
from providers.composition import create_provider_router
from providers.exceptions import ProviderValidationError
from providers.gemini import GeminiConfig, MockGeminiTransport
from providers.nemotron import (MockNemotronTransport, NemotronConfig,
    NemotronJsonExtractor, NemotronProvider, NemotronResponseParser,
    NemotronTransportResponse)
from tests.gemini_helpers import prompt_for, response_for


VALID = {"provider":"nemotron", "capability":"planning", "status":"available",
         "steps":["validate input","create plan","require founder review"]}


class ExactSmokeSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str
    capability: str
    status: str
    steps: tuple[str, str, str]


def envelope(content=VALID, **message_values):
    message={"role":"assistant", "content":content, **message_values}
    return {"id":"safe-id", "choices":[{"message":message,"finish_reason":"stop"}],
            "usage":{"prompt_tokens":8,"completion_tokens":5,"total_tokens":13}}


@pytest.mark.parametrize("content", [
    json.dumps(VALID),
    "```json\n"+json.dumps(VALID)+"\n```",
    [{"type":"text","text":json.dumps(VALID)}],
    "Final answer: "+json.dumps(VALID),
])
def test_supported_final_answer_shapes(content) -> None:
    payload, shape, field=NemotronResponseParser().parse_envelope(envelope(content), http_status_class="2xx")
    assert ExactSmokeSchema.model_validate(payload)
    assert field == "message.content" and shape.http_status_class == "2xx"


def test_reasoning_is_never_used_or_exposed() -> None:
    hidden="private hidden reasoning that must never escape"
    payload, shape, _=NemotronResponseParser().parse_envelope(
        envelope(json.dumps(VALID), reasoning_content=hidden), http_status_class="2xx")
    assert payload == VALID and shape.reasoning_field_present
    assert hidden not in str(shape.model_dump()) and hidden not in str(payload)


@pytest.mark.parametrize("content,extra,code", [
    ("", {"reasoning":"hidden"}, "PROVIDER_REASONING_WITHOUT_FINAL_ANSWER"),
    (None, {}, "EMPTY_FINAL_ANSWER"),
    (json.dumps({"a":1})+json.dumps({"b":2}), {}, "STRUCTURED_OUTPUT_INCOMPATIBLE"),
    ('{"provider":', {}, "MALFORMED_PROVIDER_RESPONSE"),
    ("prose only", {}, "MALFORMED_PROVIDER_RESPONSE"),
])
def test_invalid_final_answers_fail_safely(content, extra, code) -> None:
    with pytest.raises(ProviderValidationError) as captured:
        NemotronResponseParser().parse_envelope(envelope(content, **extra), http_status_class="2xx")
    assert captured.value.details["safe_error_code"] == code
    assert not content or str(content) not in str(captured.value)


def test_alternate_final_field_and_oversized_response() -> None:
    payload, _, field=NemotronResponseParser().parse_envelope(
        envelope(None, final_answer=json.dumps(VALID), reasoning="hidden"), http_status_class="2xx")
    assert payload == VALID and field == "message.final_answer"
    with pytest.raises(ProviderValidationError) as captured:
        NemotronJsonExtractor(maximum_characters=10).extract(json.dumps(VALID))
    assert captured.value.details["safe_error_code"] == "MALFORMED_PROVIDER_RESPONSE"


def test_exact_schema_rejects_mismatch() -> None:
    assert ExactSmokeSchema.model_validate(VALID)
    with pytest.raises(ValidationError): ExactSmokeSchema.model_validate({**VALID,"status":3})
    with pytest.raises(ValidationError): ExactSmokeSchema.model_validate({**VALID,"unknown":True})


def live_config() -> NemotronConfig:
    return NemotronConfig(enabled=True, allow_live_requests=True, api_key=SecretStr("mock-secret"))


def test_forced_and_auto_nemotron_success() -> None:
    transport=MockNemotronTransport(lambda request: NemotronTransportResponse(payload={"data":VALID}))
    forced=create_provider_router(GeminiConfig(), nemotron_config=live_config(), nemotron_transport=transport,
        routing_mode=ProviderRoutingMode.NEMOTRON_ONLY)
    result=forced.route(ProviderCapability.STRUCTURED_JSON, prompt_for(ProviderCapability.STRUCTURED_JSON))
    assert result.provider == "nemotron" and not result.fallback_used
    auto=create_provider_router(GeminiConfig(), nemotron_config=live_config(), nemotron_transport=transport,
        routing_mode=ProviderRoutingMode.AUTO, default_provider="nemotron")
    assert auto.route(ProviderCapability.STRUCTURED_JSON, prompt_for(ProviderCapability.STRUCTURED_JSON)).provider == "nemotron"


def test_auto_fails_to_gemini_and_deterministic_remains(caplog) -> None:
    invalid=MockNemotronTransport(lambda request: NemotronTransportResponse(payload={"wrong":True}))
    gemini=MockGeminiTransport(lambda request: response_for(request))
    router=create_provider_router(GeminiConfig(enabled=True,allow_live_requests=True,api_key=SecretStr("mock-secret"),maximum_retries=0),
        gemini, nemotron_config=live_config(), nemotron_transport=invalid,
        routing_mode=ProviderRoutingMode.AUTO, default_provider="nemotron")
    result=router.route(ProviderCapability.STRUCTURED_JSON, prompt_for(ProviderCapability.STRUCTURED_JSON))
    assert result.provider == "gemini" and "wrong" not in caplog.text
    forced=create_provider_router(GeminiConfig(), nemotron_config=live_config(), nemotron_transport=invalid,
        routing_mode=ProviderRoutingMode.NEMOTRON_ONLY)
    fallback=forced.route(ProviderCapability.STRUCTURED_JSON, prompt_for(ProviderCapability.STRUCTURED_JSON))
    assert fallback.provider == "deterministic" and fallback.fallback_used


def test_schema_error_is_classified_without_raw_output() -> None:
    provider=NemotronProvider(live_config(), MockNemotronTransport(
        lambda request: NemotronTransportResponse(payload={"unexpected":"secret raw output"})))
    with pytest.raises(ProviderValidationError) as captured:
        provider.generate(ProviderCapability.STRUCTURED_JSON, prompt_for(ProviderCapability.STRUCTURED_JSON))
    assert captured.value.details["safe_error_code"] == "SCHEMA_VALIDATION_FAILED"
    assert "secret raw output" not in str(captured.value)


def test_unhealthy_nemotron_is_skipped_after_one_failure() -> None:
    invalid=MockNemotronTransport(lambda request: NemotronTransportResponse(payload={"wrong":True}))
    gemini=MockGeminiTransport(lambda request: response_for(request))
    router=create_provider_router(GeminiConfig(enabled=True,allow_live_requests=True,api_key=SecretStr("mock-secret"),maximum_retries=0),
        gemini,nemotron_config=live_config(),nemotron_transport=invalid,
        routing_mode=ProviderRoutingMode.AUTO,default_provider="nemotron")
    first=router.route(ProviderCapability.STRUCTURED_JSON,prompt_for(ProviderCapability.STRUCTURED_JSON))
    second=router.route(ProviderCapability.STRUCTURED_JSON,prompt_for(ProviderCapability.STRUCTURED_JSON))
    assert first.provider==second.provider=="gemini"
    assert len(invalid.requests)==1
    health=next(item for item in router.build_state().health if item.name=="nemotron")
    assert health.status=="unhealthy"
    assert health.details["structured_output_support"]=="experimental"
