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
    GeminiParserStage,
    GeminiTransportResponse,
    GeminiValidationStage,
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


def _diagnostic(
    safe_error_code: str,
    validation_stage: GeminiValidationStage,
    parser_stage: GeminiParserStage,
    *,
    http_status: int | None = None,
    transport_completed: bool = True,
    candidates_found: bool | None = None,
    schema_validation_started: bool = False,
) -> dict[str, object]:
    return {
        "safe_error_code": safe_error_code,
        "validation_stage": validation_stage.value,
        "http_status": http_status,
        "parser_stage": parser_stage.value,
        "transport_completed": transport_completed,
        "candidates_found": candidates_found,
        "schema_validation_started": schema_validation_started,
    }


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
            details = _diagnostic(
                "direct_parse_invalid",
                GeminiValidationStage.JSON_EXTRACTION,
                GeminiParserStage.JSON_EXTRACTION,
                transport_completed=False,
            )
            decoded = self._decode_structured_text(payload, details=details)
            return model_type.model_validate(decoded)
        except ProviderValidationError:
            raise
        except (ValueError, TypeError, PydanticValidationError) as error:
            raise ProviderValidationError(
                "Gemini response failed JSON or typed validation.",
                provider_name="gemini",
                details=_diagnostic(
                    "direct_parse_invalid",
                    GeminiValidationStage.TYPED_SCHEMA,
                    GeminiParserStage.TYPED_SCHEMA,
                    transport_completed=False,
                    schema_validation_started=True,
                ),
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
        status = response.status_code
        if len(response.response_body) > self.maximum_response_characters:
            raise ProviderValidationError(
                "Gemini response exceeded the parser size limit.",
                provider_name="gemini",
                details=_diagnostic(
                    "response_too_large",
                    GeminiValidationStage.RESPONSE_ENVELOPE,
                    GeminiParserStage.ENVELOPE,
                    http_status=status,
                ),
                retryable=False,
            )
        if not response.response_body.strip():
            raise ProviderValidationError(
                "Gemini response body was empty.",
                provider_name="gemini",
                details=_diagnostic(
                    "empty_response",
                    GeminiValidationStage.RESPONSE_ENVELOPE,
                    GeminiParserStage.ENVELOPE,
                    http_status=status,
                ),
                retryable=False,
            )
        envelope = self._decode_json_object(
            response.response_body,
            "envelope",
            details=_diagnostic(
                "invalid_envelope",
                GeminiValidationStage.RESPONSE_ENVELOPE,
                GeminiParserStage.ENVELOPE,
                http_status=status,
            ),
        )
        prompt_feedback = envelope.get("promptFeedback")
        if isinstance(prompt_feedback, dict) and prompt_feedback.get("blockReason"):
            raise ProviderSafetyError(
                "Gemini prompt was refused for safety.",
                provider_name="gemini",
                details=_diagnostic(
                    "safety_rejected",
                    GeminiValidationStage.SAFETY,
                    GeminiParserStage.SAFETY,
                    http_status=status,
                    candidates_found=False,
                ),
                retryable=False,
            )
        candidates = envelope.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise ProviderValidationError(
                "Gemini response did not contain a candidate.",
                provider_name="gemini",
                details=_diagnostic(
                    "missing_candidates",
                    GeminiValidationStage.CANDIDATE,
                    GeminiParserStage.CANDIDATES,
                    http_status=status,
                    candidates_found=False,
                ),
                retryable=False,
            )
        candidate = candidates[0]
        if not isinstance(candidate, dict):
            raise ProviderValidationError(
                "Gemini candidate was malformed.",
                provider_name="gemini",
                details=_diagnostic(
                    "malformed_candidate",
                    GeminiValidationStage.CANDIDATE,
                    GeminiParserStage.CANDIDATES,
                    http_status=status,
                    candidates_found=True,
                ),
            )
        finish_reason = str(candidate.get("finishReason") or "")
        safety_metadata = {"ratings": candidate.get("safetyRatings", [])}
        text = self._candidate_text(candidate, http_status=status)
        structured = self._decode_structured_text(
            text,
            details=_diagnostic(
                "invalid_json",
                GeminiValidationStage.JSON_EXTRACTION,
                GeminiParserStage.JSON_EXTRACTION,
                http_status=status,
                candidates_found=True,
            ),
        )
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
                details=_diagnostic(
                    "safety_rejected",
                    GeminiValidationStage.SAFETY,
                    GeminiParserStage.SAFETY,
                    http_status=status,
                    candidates_found=True,
                ),
                retryable=False,
            ) from error
        try:
            output_type = provider_output_model(capability)
            typed_payload = output_type.model_validate(structured)
        except PydanticValidationError as error:
            raise ProviderValidationError(
                "Gemini structured content failed the expected schema.",
                provider_name="gemini",
                details=_diagnostic(
                    "typed_schema_invalid",
                    GeminiValidationStage.TYPED_SCHEMA,
                    GeminiParserStage.TYPED_SCHEMA,
                    http_status=status,
                    candidates_found=True,
                    schema_validation_started=True,
                ),
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
        common = {
            "validation_stage": GeminiValidationStage.HTTP_STATUS,
            "parser_stage": GeminiParserStage.HTTP_STATUS,
            "http_status": status,
        }
        if status in {401, 403}:
            raise ProviderAuthenticationError(
                "Gemini authentication was rejected; credentials were redacted.",
                provider_name="gemini",
                details=_diagnostic("authentication_rejected", **common),
                retryable=False,
            )
        if status == 429:
            raise ProviderRateLimitError(
                "Gemini request was rate limited.",
                provider_name="gemini",
                details=_diagnostic("rate_limited", **common),
                retryable=True,
            )
        if status == 408:
            raise ProviderTimeoutError(
                "Gemini request timed out.",
                provider_name="gemini",
                details=_diagnostic("request_timeout", **common),
                retryable=True,
            )
        if status == 404:
            raise ProviderUnavailableError(
                "The configured Gemini model was unavailable.",
                provider_name="gemini",
                details=_diagnostic("model_unavailable", **common),
                retryable=False,
            )
        if status >= 500:
            raise ProviderUnavailableError(
                "Gemini reported a transient provider failure.",
                provider_name="gemini",
                details=_diagnostic("provider_failure", **common),
                retryable=True,
            )
        raise ProviderValidationError(
            "Gemini rejected the structured request.",
            provider_name="gemini",
            details=_diagnostic(
                response.safe_error_code or "invalid_request", **common
            ),
            retryable=False,
        )

    @staticmethod
    def _candidate_text(
        candidate: dict[str, Any],
        *,
        http_status: int,
    ) -> str:
        content = candidate.get("content")
        parts = content.get("parts") if isinstance(content, dict) else None
        if not isinstance(parts, list) or not parts:
            raise ProviderValidationError(
                "Gemini candidate content was empty.",
                provider_name="gemini",
                details=_diagnostic(
                    "empty_candidate",
                    GeminiValidationStage.CANDIDATE,
                    GeminiParserStage.CANDIDATES,
                    http_status=http_status,
                    candidates_found=True,
                ),
            )
        values = [part.get("text") for part in parts if isinstance(part, dict)]
        text = "".join(value for value in values if isinstance(value, str)).strip()
        if not text:
            raise ProviderValidationError(
                "Gemini candidate text was empty.",
                provider_name="gemini",
                details=_diagnostic(
                    "empty_candidate",
                    GeminiValidationStage.CANDIDATE,
                    GeminiParserStage.CANDIDATES,
                    http_status=http_status,
                    candidates_found=True,
                ),
            )
        return text

    @staticmethod
    def _decode_json_object(
        payload: str,
        label: str,
        *,
        details: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        try:
            decoded = json.loads(payload)
        except (json.JSONDecodeError, TypeError) as error:
            raise ProviderValidationError(
                f"Gemini {label} was not valid JSON.",
                details=details,
                retryable=False,
            ) from error
        if not isinstance(decoded, dict):
            raise ProviderValidationError(
                f"Gemini {label} must be a JSON object.", details=details
            )
        return decoded

    @classmethod
    def _decode_structured_text(
        cls,
        payload: str,
        *,
        details: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        cleaned = payload.strip()
        fenced = _FENCED_JSON.fullmatch(cleaned)
        if fenced:
            cleaned = fenced.group(1)
        elif cleaned.startswith("```") or not (
            cleaned.startswith("{") and cleaned.endswith("}")
        ):
            raise ProviderValidationError(
                "Gemini structured content contained unsupported surrounding text.",
                details=details,
            )
        return cls._decode_json_object(
            cleaned,
            "structured content",
            details=details,
        )

    @staticmethod
    def _nonnegative_int(value: object) -> int:
        return int(value) if isinstance(value, int) and value >= 0 else 0

    @staticmethod
    def _warnings_for(capability: ProviderCapability) -> list[str]:
        if capability in {ProviderCapability.RESEARCH, ProviderCapability.ANALYTICS}:
            return ["Verify AI-assisted claims against attributable evidence."]
        return ["AI advice is additive and requires normal AuraAI review."]
