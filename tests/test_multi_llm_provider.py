"""Mock-only tests for provider-independent multi-LLM routing."""
from __future__ import annotations
from pydantic import SecretStr
from providers import ProviderCapability, ProviderRoutingMode, build_department_prompt, PromptCategory
from providers.composition import create_provider_router
from providers.exceptions import ProviderTimeoutError
from providers.gemini import GeminiConfig, MockGeminiTransport
from providers.nemotron import NemotronConfig, NemotronProvider, NemotronTransportResponse, MockNemotronTransport
from providers.provider_result import ProviderResult
from tests.gemini_helpers import response_for


def prompt():
    return build_department_prompt("multi_llm_test", PromptCategory.STRATEGY, "safe architecture")


def gemini_config() -> GeminiConfig:
    return GeminiConfig(enabled=True, allow_live_requests=True, api_key=SecretStr("unit-test-secret"), maximum_retries=0)


def nemotron_config() -> NemotronConfig:
    return NemotronConfig(enabled=True, allow_live_requests=True, api_key=SecretStr("unit-test-secret"))


def nemotron_transport(payload: dict | None = None) -> MockNemotronTransport:
    return MockNemotronTransport(lambda request: NemotronTransportResponse(payload=payload or {"text": "Nemotron result"}, input_tokens=4, output_tokens=3))


def test_gemini_only_and_auto_routing() -> None:
    gemini=MockGeminiTransport(lambda request: response_for(request))
    only=create_provider_router(gemini_config(), gemini, nemotron_config=nemotron_config(),
        nemotron_transport=nemotron_transport(), routing_mode=ProviderRoutingMode.GEMINI_ONLY)
    assert only.route(ProviderCapability.REASONING, prompt()).provider == "gemini"
    auto=create_provider_router(gemini_config(), MockGeminiTransport(lambda request: response_for(request)),
        nemotron_config=nemotron_config(), nemotron_transport=nemotron_transport(),
        routing_mode=ProviderRoutingMode.AUTO, default_provider="gemini")
    assert auto.route(ProviderCapability.PLANNING, prompt()).provider == "gemini"


def test_nemotron_only_structured_json_and_common_interface() -> None:
    transport=nemotron_transport({"data": {"step": "review", "approved": False}})
    router=create_provider_router(GeminiConfig(), nemotron_config=nemotron_config(), nemotron_transport=transport,
        routing_mode=ProviderRoutingMode.NEMOTRON_ONLY)
    result=router.route(ProviderCapability.STRUCTURED_JSON, prompt())
    assert isinstance(result, ProviderResult)
    assert result.provider == "nemotron" and result.output.data["approved"] is False
    assert isinstance(NemotronProvider(nemotron_config(), transport).generate(ProviderCapability.STRUCTURED_JSON, prompt()), ProviderResult)


def test_auto_fails_over_from_gemini_to_nemotron() -> None:
    def unavailable(_request):
        raise ProviderTimeoutError("Gemini timed out safely.", provider_name="gemini")
    router=create_provider_router(gemini_config(), MockGeminiTransport(unavailable), nemotron_config=nemotron_config(),
        nemotron_transport=nemotron_transport(), routing_mode=ProviderRoutingMode.AUTO, default_provider="gemini")
    assert router.route(ProviderCapability.REASONING, prompt()).provider == "nemotron"


def test_timeout_falls_back_without_secret_leakage(caplog) -> None:
    secret="never-log-this-key"
    def timeout(_request):
        raise ProviderTimeoutError("Request timed out safely.", provider_name="nemotron")
    config=NemotronConfig(enabled=True, allow_live_requests=True, api_key=SecretStr(secret))
    router=create_provider_router(GeminiConfig(), nemotron_config=config,
        nemotron_transport=MockNemotronTransport(timeout), routing_mode=ProviderRoutingMode.NEMOTRON_ONLY)
    result=router.route(ProviderCapability.CODING, prompt())
    assert result.provider == "deterministic" and result.fallback_used
    assert secret not in caplog.text and secret not in str(config) and secret not in str(config.model_dump())


def test_cli_lists_safely_without_calls(monkeypatch, capsys) -> None:
    from providers.cli import main
    monkeypatch.setenv("NVIDIA_API_KEY", "cli-secret-value")
    monkeypatch.setenv("AURAAI_NEMOTRON_ENABLED", "true")
    assert main(["--list"]) == 0
    output=capsys.readouterr().out
    assert "provider=gemini" in output and "provider=nemotron" in output
    assert "cli-secret-value" not in output
