"""Transport-injected Gemini REST boundary with no SDK dependency."""

from __future__ import annotations

import json
import re
import socket
from dataclasses import dataclass
from enum import StrEnum
from threading import Event
from time import perf_counter
from typing import Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from providers.exceptions import ProviderTimeoutError, ProviderUnavailableError
from providers.gemini.config import ALLOWED_GEMINI_HOSTS
from providers.gemini.models import (
    GeminiParserStage,
    GeminiRequest,
    GeminiTransportResponse,
    GeminiValidationStage,
)
from providers.gemini.redaction import redact_sensitive_text


MAX_REQUEST_BYTES = 256_000
MAX_RESPONSE_BYTES = 2_000_000


class GeminiTransportErrorCode(StrEnum):
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    NETWORK_UNAVAILABLE = "network_unavailable"
    REQUEST_TOO_LARGE = "request_too_large"
    RESPONSE_TOO_LARGE = "response_too_large"
    INVALID_ENDPOINT = "invalid_endpoint"
    INVALID_RESPONSE_ENCODING = "invalid_response_encoding"


class GeminiTransportError(ProviderUnavailableError):
    """Safe transport error carrying only bounded diagnostic metadata."""

    def __init__(
        self,
        message: str,
        *,
        code: GeminiTransportErrorCode,
        retryable: bool,
    ) -> None:
        self.safe_code = code.value
        super().__init__(
            redact_sensitive_text(message),
            provider_name="gemini",
            details={
                "safe_error_code": self.safe_code,
                "validation_stage": GeminiValidationStage.TRANSPORT.value,
                "http_status": None,
                "parser_stage": GeminiParserStage.NOT_STARTED.value,
                "transport_completed": False,
                "candidates_found": None,
                "schema_validation_started": False,
            },
            retryable=retryable,
        )


@dataclass(frozen=True, slots=True)
class HttpExecutionResult:
    status_code: int
    body: bytes
    headers: dict[str, str]


class HttpExecutor(Protocol):
    def __call__(
        self,
        request: Request,
        timeout_seconds: float,
        maximum_response_bytes: int,
    ) -> HttpExecutionResult: ...


class GeminiTransport(Protocol):
    def send(
        self,
        request: GeminiRequest,
        *,
        timeout_seconds: float,
        cancel_event: Event | None = None,
    ) -> GeminiTransportResponse: ...


class MockGeminiTransport:
    """Deterministic test transport; no sockets or SDK objects are used."""

    def __init__(
        self,
        responder: Callable[[GeminiRequest], GeminiTransportResponse],
    ) -> None:
        self._responder = responder
        self.requests: list[GeminiRequest] = []

    def send(
        self,
        request: GeminiRequest,
        *,
        timeout_seconds: float,
        cancel_event: Event | None = None,
    ) -> GeminiTransportResponse:
        del timeout_seconds
        if cancel_event is not None and cancel_event.is_set():
            raise GeminiTransportError(
                "Gemini request was cancelled before execution.",
                code=GeminiTransportErrorCode.CANCELLED,
                retryable=False,
            )
        self.requests.append(request)
        return self._responder(request)


class UnavailableGeminiTransport:
    """Default transport that guarantees no live request occurs."""

    def send(
        self,
        request: GeminiRequest,
        *,
        timeout_seconds: float,
        cancel_event: Event | None = None,
    ) -> GeminiTransportResponse:
        del request, timeout_seconds, cancel_event
        raise GeminiTransportError(
            "No Gemini transport was explicitly configured.",
            code=GeminiTransportErrorCode.NETWORK_UNAVAILABLE,
            retryable=False,
        )


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        return None


def standard_library_http_executor(
    request: Request,
    timeout_seconds: float,
    maximum_response_bytes: int,
) -> HttpExecutionResult:
    """Execute one bounded HTTPS request without following redirects."""

    opener = build_opener(_NoRedirectHandler())
    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            body = response.read(maximum_response_bytes + 1)
            if len(body) > maximum_response_bytes:
                raise GeminiTransportError(
                    "Gemini response exceeded the configured size limit.",
                    code=GeminiTransportErrorCode.RESPONSE_TOO_LARGE,
                    retryable=False,
                )
            return HttpExecutionResult(
                status_code=response.status,
                body=body,
                headers=dict(response.headers.items()),
            )
    except HTTPError as error:
        body = error.read(maximum_response_bytes + 1)
        if len(body) > maximum_response_bytes:
            body = b""
        return HttpExecutionResult(
            status_code=error.code,
            body=body,
            headers=dict(error.headers.items()) if error.headers else {},
        )
    except (TimeoutError, socket.timeout) as error:
        raise ProviderTimeoutError(
            "Gemini request timed out.",
            provider_name="gemini",
            retryable=True,
        ) from error
    except URLError as error:
        raise GeminiTransportError(
            "Gemini network transport was unavailable.",
            code=GeminiTransportErrorCode.NETWORK_UNAVAILABLE,
            retryable=True,
        ) from error


class HttpGeminiTransport:
    """Safe REST transport enabled only through explicit composition."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        executor: HttpExecutor = standard_library_http_executor,
        maximum_request_bytes: int = MAX_REQUEST_BYTES,
        maximum_response_bytes: int = MAX_RESPONSE_BYTES,
    ) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_GEMINI_HOSTS:
            raise ValueError("Gemini transport requires the allowlisted HTTPS host.")
        if not api_key.strip():
            raise ValueError("Gemini transport requires an injected API key.")
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key.strip()
        self._executor = executor
        self._maximum_request_bytes = maximum_request_bytes
        self._maximum_response_bytes = maximum_response_bytes

    def send(
        self,
        request: GeminiRequest,
        *,
        timeout_seconds: float,
        cancel_event: Event | None = None,
    ) -> GeminiTransportResponse:
        if cancel_event is not None and cancel_event.is_set():
            raise GeminiTransportError(
                "Gemini request was cancelled before execution.",
                code=GeminiTransportErrorCode.CANCELLED,
                retryable=False,
            )
        body = json.dumps(self._request_payload(request)).encode("utf-8")
        if len(body) > self._maximum_request_bytes:
            raise GeminiTransportError(
                "Gemini request exceeded the configured size limit.",
                code=GeminiTransportErrorCode.REQUEST_TOO_LARGE,
                retryable=False,
            )
        url = (
            f"{self._base_url}/models/{quote(request.model, safe='')}:"
            "generateContent"
        )
        http_request = Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "x-goog-api-key": self._api_key,
            },
            method="POST",
        )
        started = perf_counter()
        try:
            result = self._executor(
                http_request,
                timeout_seconds,
                self._maximum_response_bytes,
            )
        except Exception as error:
            if isinstance(error, (GeminiTransportError, ProviderTimeoutError)):
                raise
            raise GeminiTransportError(
                "Gemini HTTP execution failed safely.",
                code=GeminiTransportErrorCode.NETWORK_UNAVAILABLE,
                retryable=True,
            ) from error
        try:
            text = result.body.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise GeminiTransportError(
                "Gemini response was not valid UTF-8.",
                code=GeminiTransportErrorCode.INVALID_RESPONSE_ENCODING,
                retryable=False,
            ) from error
        safe_error_code = None
        if result.status_code == 400 and request.founder_smoke_test_diagnostics:
            safe_error_code = self._classify_http_400(text)
            text = ""
        return GeminiTransportResponse(
            request_id=request.request_id,
            status_code=result.status_code,
            response_body=text,
            latency_ms=(perf_counter() - started) * 1000,
            provider_request_id=result.headers.get("x-request-id"),
            safe_error_code=safe_error_code,
        )

    @staticmethod
    def _request_payload(request: GeminiRequest) -> dict[str, object]:
        generation_config: dict[str, object] = {
            "maxOutputTokens": request.maximum_output_tokens,
            "responseFormat": {
                "text": {
                    "mimeType": "application/json",
                    "schema": request.response_schema,
                }
            },
        }
        if not request.model.startswith("gemini-3.5"):
            generation_config.update(
                temperature=request.temperature,
                topP=request.top_p,
            )
        return {
            "systemInstruction": {"parts": [{"text": request.system_instruction}]},
            "contents": [{"role": "user", "parts": [{"text": request.user_prompt}]}],
            "generationConfig": generation_config,
            "safetySettings": request.safety_settings,
        }

    @staticmethod
    def _classify_http_400(response_body: str) -> str:
        """Classify a Google error without retaining or returning its content."""

        try:
            payload = json.loads(response_body)
        except (json.JSONDecodeError, TypeError):
            return "invalid_request"
        error = payload.get("error") if isinstance(payload, dict) else None
        message = error.get("message") if isinstance(error, dict) else None
        if not isinstance(message, str):
            return "invalid_request"
        normalized = re.sub(r"[^a-z0-9_ ]", " ", message.lower())
        classifications = (
            (
                (
                    "temperature",
                    "topp",
                    "top_p",
                    "top p",
                    "topk",
                    "top_k",
                ),
                "unsupported_generation_parameter",
            ),
            (
                ("responseformat", "response_format", "response format"),
                "unsupported_response_format",
            ),
            (
                ("responseschema", "response_schema", "schema"),
                "invalid_response_schema",
            ),
            (
                ("safetysettings", "safety_settings", "harm_category"),
                "invalid_safety_settings",
            ),
            (("contents", "parts", "role"), "invalid_contents"),
            (("model",), "invalid_model"),
        )
        for markers, safe_code in classifications:
            if any(marker in normalized for marker in markers):
                return safe_code
        return "invalid_request"
