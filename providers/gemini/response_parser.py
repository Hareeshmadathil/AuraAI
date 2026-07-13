"""Strict Gemini envelope, safety, JSON, and typed response parsing."""

from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from pydantic import ValidationError as PydanticValidationError

from core import AuraBaseModel, utc_now
from providers.exceptions import (
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderSafetyError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    ProviderValidationError,
)
from providers.gemini.models import (
    GeminiTransportResponse,
    GeminiValidatedResponse,
)
from providers.gemini.safety import GeminiSafetyValidator
from providers.models import (
    ProviderCapability,
    ProviderUsage,
    ReviewOutput,
    provider_output_model,
)


ModelT = TypeVar("ModelT", bound=AuraBaseModel)
_FENCED_JSON = re.compile(r"^```(?:json)?\s*(\{.*\})\s*```$", re.DOTALL)


class GeminiResponseParser:
    """Convert a bounded transport response into neutral AuraAI models."""

    def __init__(
        self,
        safety_validator: GeminiSafetyValidator | None = None,
        maximum_response_characters: int = 2_000_000,
    ) -> None:
        self.safety_validator = safety_validator or GeminiSafetyValidator()
        self.maximum_response_characters = maximum_response_characters

    def parse(self, payload: str, model_type: type[ModelT]) -> ModelT:
        """Preserve the original direct strict-JSON parsing API."""

        try:
            decoded = self._decode_structured_text(payload)
            return model_type.model_validate(decoded)
        except (ValueError, TypeError, PydanticValidationError) as error:
            raise ProviderValidationError(
                "Gemini response failed JSON or typed validation.",
                provider_name="gemini",
                retryable=False,
            ) from error

    def parse_transport_response(
        self,
        response: GeminiTransportResponse,
        capability: ProviderCapability,
        *,
        model: str,
        prompt_metadata: dict[str, str | int],
    ) -> GeminiValidatedResponse:
        self._validate_http_status(response)
        if len(response.response_body) > self.maximum_response_characters:
            raise ProviderValidationError(
                "Gemini response exceeded the parser size limit.",
                provider_name="gemini",
                retryable=False,
            )
        envelope = self._decode_json_object(response.response_body, "envelope")
        prompt_feedback = envelope.get("promptFeedback")
        if isinstance(prompt_feedback, dict) and prompt_feedback.get("blockReason"):
            raise ProviderSafetyError(
                "Gemini prompt was refused for safety.",
                provider_name="gemini",
                retryable=False,
            )
        candidates = envelope.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise ProviderValidationError(
                "Gemini response did not contain a candidate.",
                provider_name="gemini",
                retryable=False,
            )
        candidate = candidates[0]
        if not isinstance(candidate, dict):
            raise ProviderValidationError("Gemini candidate was malformed.")
        finish_reason = str(candidate.get("finishReason") or "")
        safety_metadata = {"ratings": candidate.get("safetyRatings", [])}
        text = self._candidate_text(candidate)
        structured = self._decode_structured_text(text)
        try:
            safety_result = self.safety_validator.inspect(
                structured,
                finish_reason=finish_reason,
                safety_metadata=safety_metadata,
            )
        except ProviderValidationError as error:
            raise ProviderSafetyError(
                str(error),
                provider_name="gemini",
                retryable=False,
            ) from error
        try:
            output_type = provider_output_model(capability)
            typed_payload = output_type.model_validate(structured)
        except PydanticValidationError as error:
            raise ProviderValidationError(
                "Gemini structured content failed the expected schema.",
                provider_name="gemini",
                retryable=False,
            ) from error
        validation_warnings = self._warnings_for(capability)
        if capability == ProviderCapability.REVIEW and isinstance(
            typed_payload, ReviewOutput
        ):
            typed_payload = typed_payload.model_copy(update={"approved": False})
            validation_warnings.append(
                "Provider review advice cannot grant AuraAI approval."
            )
        usage_data = envelope.get("usageMetadata", {})
        if not isinstance(usage_data, dict):
            usage_data = {}
        input_tokens = self._nonnegative_int(
            usage_data.get("promptTokenCount") or response.input_token_count
        )
        output_tokens = self._nonnegative_int(
            usage_data.get("candidatesTokenCount") or response.output_token_count
        )
        usage = ProviderUsage(
            request_id=response.request_id,
            provider="gemini",
            model=model,
            capability=capability,
            tokens_requested=input_tokens + output_tokens,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=response.latency_ms,
            completed_at=utc_now(),
            prompt_template_id=str(prompt_metadata.get("template_id") or ""),
            prompt_version=str(prompt_metadata.get("version") or ""),
            prompt_hash=str(prompt_metadata.get("hash") or ""),
            approximate_input_bytes=int(prompt_metadata.get("input_bytes") or 0),
        )
        return GeminiValidatedResponse(
            request_id=response.request_id,
            capability=capability,
            typed_payload=typed_payload,
            usage=usage,
            safety_result=safety_result,
            validation_warnings=validation_warnings,
        )

    @staticmethod
    def _validate_http_status(response: GeminiTransportResponse) -> None:
        status = response.status_code
        if 200 <= status < 300:
            return
        if status in {401, 403}:
            raise ProviderAuthenticationError(
                "Gemini authentication was rejected; credentials were redacted.",
                provider_name="gemini",
                details={"safe_error_code": "authentication_rejected"},
                retryable=False,
            )
        if status == 429:
            raise ProviderRateLimitError(
                "Gemini request was rate limited.",
                provider_name="gemini",
                details={"safe_error_code": "rate_limited"},
                retryable=True,
            )
        if status == 408:
            raise ProviderTimeoutError(
                "Gemini request timed out.",
                provider_name="gemini",
                retryable=True,
            )
        if status == 404:
            raise ProviderUnavailableError(
                "The configured Gemini model was unavailable.",
                provider_name="gemini",
                details={"safe_error_code": "model_unavailable"},
                retryable=False,
            )
        if status >= 500:
            raise ProviderUnavailableError(
                "Gemini reported a transient provider failure.",
                provider_name="gemini",
                details={"safe_error_code": "provider_failure"},
                retryable=True,
            )
        raise ProviderValidationError(
            "Gemini rejected the structured request.",
            provider_name="gemini",
            details={"safe_error_code": "invalid_request"},
            retryable=False,
        )

    @staticmethod
    def _candidate_text(candidate: dict[str, Any]) -> str:
        content = candidate.get("content")
        parts = content.get("parts") if isinstance(content, dict) else None
        if not isinstance(parts, list) or not parts:
            raise ProviderValidationError("Gemini candidate content was empty.")
        values = [part.get("text") for part in parts if isinstance(part, dict)]
        text = "".join(value for value in values if isinstance(value, str)).strip()
        if not text:
            raise ProviderValidationError("Gemini candidate text was empty.")
        return text

    @staticmethod
    def _decode_json_object(payload: str, label: str) -> dict[str, Any]:
        try:
            decoded = json.loads(payload)
        except (json.JSONDecodeError, TypeError) as error:
            raise ProviderValidationError(
                f"Gemini {label} was not valid JSON.", retryable=False
            ) from error
        if not isinstance(decoded, dict):
            raise ProviderValidationError(f"Gemini {label} must be a JSON object.")
        return decoded

    @classmethod
    def _decode_structured_text(cls, payload: str) -> dict[str, Any]:
        cleaned = payload.strip()
        fenced = _FENCED_JSON.fullmatch(cleaned)
        if fenced:
            cleaned = fenced.group(1)
        elif cleaned.startswith("```") or not (
            cleaned.startswith("{") and cleaned.endswith("}")
        ):
            raise ProviderValidationError(
                "Gemini structured content contained unsupported surrounding text."
            )
        return cls._decode_json_object(cleaned, "structured content")

    @staticmethod
    def _nonnegative_int(value: object) -> int:
        return int(value) if isinstance(value, int) and value >= 0 else 0

    @staticmethod
    def _warnings_for(capability: ProviderCapability) -> list[str]:
        if capability in {ProviderCapability.RESEARCH, ProviderCapability.ANALYTICS}:
            return ["Verify AI-assisted claims against attributable evidence."]
        return ["AI advice is additive and requires normal AuraAI review."]
