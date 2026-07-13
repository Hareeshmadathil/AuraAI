"""Bounded HTTP and mock transport tests with no live requests."""

import json
from threading import Event

import pytest

from providers import ProviderCapability
from providers.gemini import GeminiConfig, GeminiPromptBuilder
from providers.gemini.transport import (
    GeminiTransportError,
    HttpExecutionResult,
    HttpGeminiTransport,
    MockGeminiTransport,
    UnavailableGeminiTransport,
)
from tests.gemini_helpers import prompt_for


def build_request():
    config = GeminiConfig()
    return GeminiPromptBuilder().build_request(
        ProviderCapability.RESEARCH,
        prompt_for(ProviderCapability.RESEARCH),
        config,
    )


def test_http_transport_uses_injected_executor_and_safe_json() -> None:
    observed: dict[str, object] = {}

    def executor(request, timeout, maximum):
        payload = json.loads(request.data)
        observed.update(
            url=request.full_url,
            timeout=timeout,
            maximum=maximum,
            content_type=request.headers["Content-type"],
            api_key=request.headers["X-goog-api-key"],
            payload=payload,
        )
        return HttpExecutionResult(200, b'{"candidates":[]}', {})

    transport = HttpGeminiTransport(
        base_url="https://generativelanguage.googleapis.com/v1beta",
        api_key="fake-transport-key",
        executor=executor,
    )
    response = transport.send(build_request(), timeout_seconds=3)
    assert response.status_code == 200
    assert observed["timeout"] == 3
    assert observed["content_type"] == "application/json"
    assert observed["api_key"] == "fake-transport-key"
    assert observed["url"].endswith(
        "/v1beta/models/gemini-3.5-flash:generateContent"
    )
    assert "?key=" not in str(observed["url"])
    generation = observed["payload"]["generationConfig"]
    assert generation["responseFormat"]["text"]["mimeType"] == "application/json"
    assert "responseSchema" not in generation


def test_transport_enforces_https_and_allowlisted_host() -> None:
    with pytest.raises(ValueError, match="allowlisted HTTPS"):
        HttpGeminiTransport(base_url="http://example.com", api_key="fake")


def test_transport_rejects_oversized_request() -> None:
    transport = HttpGeminiTransport(
        base_url="https://generativelanguage.googleapis.com/v1beta",
        api_key="fake-key",
        executor=lambda *_: HttpExecutionResult(200, b"{}", {}),
        maximum_request_bytes=10,
    )
    with pytest.raises(GeminiTransportError, match="size limit"):
        transport.send(build_request(), timeout_seconds=1)


def test_unavailable_transport_never_attempts_network() -> None:
    with pytest.raises(GeminiTransportError, match="explicitly configured"):
        UnavailableGeminiTransport().send(build_request(), timeout_seconds=1)


def test_mock_transport_supports_structured_cancellation() -> None:
    cancelled = Event()
    cancelled.set()
    transport = MockGeminiTransport(
        lambda request: (_ for _ in ()).throw(
            AssertionError("Cancelled request must not reach responder")
        )
    )
    with pytest.raises(GeminiTransportError) as raised:
        transport.send(
            build_request(),
            timeout_seconds=1,
            cancel_event=cancelled,
        )
    assert raised.value.details["safe_error_code"] == "cancelled"


def test_transport_exception_does_not_expose_key() -> None:
    secret = "fake-key-that-must-not-leak"

    def executor(*_):
        raise RuntimeError(f"failed URL key={secret}")

    transport = HttpGeminiTransport(
        base_url="https://generativelanguage.googleapis.com/v1beta",
        api_key=secret,
        executor=executor,
    )
    with pytest.raises(GeminiTransportError) as raised:
        transport.send(build_request(), timeout_seconds=1)
    assert secret not in str(raised.value)
