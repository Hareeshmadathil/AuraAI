"""Dependency-injected transport boundary for NVIDIA Nemotron."""
from __future__ import annotations
from collections.abc import Callable
import json
from time import perf_counter
from typing import Protocol
import urllib.error
import urllib.request

from providers.exceptions import (
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    ProviderValidationError,
)
from providers.nemotron.config import ALLOWED_NVIDIA_HOSTS
from providers.nemotron.http_decoder import NemotronHttpDecoder
from providers.nemotron.models import NemotronRequest, NemotronTransportResponse
from providers.nemotron.response_parser import NemotronResponseParser
from urllib.parse import urlparse


class NemotronTransport(Protocol):
    def send(self, request: NemotronRequest, *, timeout_seconds: float) -> NemotronTransportResponse: ...


class MockNemotronTransport:
    """In-memory transport used by tests; never performs I/O."""
    def __init__(self, responder: Callable[[NemotronRequest], NemotronTransportResponse]) -> None:
        self._responder = responder
        self.requests: list[NemotronRequest] = []
        self.timeouts: list[float] = []

    def send(self, request: NemotronRequest, *, timeout_seconds: float) -> NemotronTransportResponse:
        self.requests.append(request)
        self.timeouts.append(timeout_seconds)
        return self._responder(request)


class UnavailableNemotronTransport:
    def send(self, request: NemotronRequest, *, timeout_seconds: float) -> NemotronTransportResponse:
        del request, timeout_seconds
        raise ProviderUnavailableError("No Nemotron transport was explicitly configured.", provider_name="nemotron", retryable=False)


class HttpNemotronTransport:
    """Bounded NVIDIA chat-completions transport with content-free errors."""

    def __init__(self, *, base_url: str, api_key: str,
                 response_parser: NemotronResponseParser | None = None,
                 maximum_response_bytes: int = 2_000_000) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_NVIDIA_HOSTS:
            raise ValueError("Nemotron transport requires the allowlisted HTTPS host.")
        if not api_key.strip():
            raise ValueError("Nemotron transport requires an injected API key.")
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._api_key = api_key
        self.response_parser = response_parser or NemotronResponseParser()
        self.maximum_response_bytes = maximum_response_bytes
        self.http_decoder = NemotronHttpDecoder(maximum_response_bytes)
        self.last_safe_diagnostics: dict[str, object] = {}
        self.last_final_answer_field = "unknown"

    def send(self, request: NemotronRequest, *, timeout_seconds: float) -> NemotronTransportResponse:
        body = json.dumps({
            "model": request.model,
            "messages": [
                {"role": "system", "content": "Return only one final JSON object matching the requested schema. Do not include reasoning."},
                {"role": "user", "content": request.prompt},
            ],
            "temperature": 0 if request.capability.value == "structured_json" else request.temperature,
            "max_tokens": request.maximum_output_tokens,
            "stream": False,
        }, separators=(",", ":")).encode("utf-8")
        http_request = urllib.request.Request(self._url, data=body,
            headers={"Authorization": "Bearer " + self._api_key, "Content-Type": "application/json"}, method="POST")
        started = perf_counter()
        try:
            with urllib.request.urlopen(http_request, timeout=timeout_seconds) as response:
                status = response.status
                raw = response.read(self.maximum_response_bytes + 1)
                response_headers = dict(response.headers.items())
        except urllib.error.HTTPError as error:
            self._raise_http(error.code)
        except (TimeoutError, urllib.error.URLError) as error:
            if isinstance(getattr(error, "reason", None), TimeoutError) or isinstance(error, TimeoutError):
                raise ProviderTimeoutError("Nemotron request timed out.", provider_name="nemotron", retryable=False) from None
            raise ProviderUnavailableError("Nemotron transport was unavailable.", provider_name="nemotron", retryable=False) from None
        try:
            envelope, http_diagnostics = self.http_decoder.decode(raw, response_headers, status=status)
        except ProviderValidationError as error:
            self.last_safe_diagnostics = dict(error.details)
            raise
        self.last_safe_diagnostics = dict(http_diagnostics)
        payload, shape, field = self.response_parser.parse_envelope(envelope, http_status_class=f"{status // 100}xx")
        self.last_safe_diagnostics = {**http_diagnostics, **shape.model_dump(mode="json")}
        self.last_final_answer_field = field
        if request.capability.value == "structured_json" and set(payload) != {"data"}:
            payload = {"data": payload}
        usage = shape.usage
        return NemotronTransportResponse(payload=payload,
            input_tokens=usage.get("prompt_tokens", 0), output_tokens=usage.get("completion_tokens", 0),
            latency_ms=(perf_counter() - started) * 1000, http_status_class=shape.http_status_class,
            final_answer_field=field, safe_diagnostics=self.last_safe_diagnostics)

    @staticmethod
    def _raise_http(status: int) -> None:
        details={"safe_error_code": "PROVIDER_ERROR", "http_status": status}
        if status in {401,403}:
            raise ProviderAuthenticationError("Nemotron authentication was rejected.", provider_name="nemotron", details=details, retryable=False)
        if status == 429:
            raise ProviderRateLimitError("Nemotron request was rate limited.", provider_name="nemotron", details=details, retryable=False)
        if status in {408,504}:
            raise ProviderTimeoutError("Nemotron request timed out.", provider_name="nemotron", details=details, retryable=False)
        raise ProviderUnavailableError("Nemotron provider request failed.", provider_name="nemotron", details=details, retryable=False)
