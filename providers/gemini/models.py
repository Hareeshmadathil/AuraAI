"""Typed request, transport, validation, and safety models for Gemini."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field, field_validator

from core import AuraBaseModel, utc_now
from providers.models import ProviderCapability, ProviderOutput, ProviderUsage


class GeminiValidationStage(StrEnum):
    """Safe high-level boundary reached before a Gemini failure."""

    TRANSPORT = "transport"
    HTTP_STATUS = "http_status"
    RESPONSE_ENVELOPE = "response_envelope"
    CANDIDATE = "candidate"
    JSON_EXTRACTION = "json_extraction"
    SAFETY = "safety"
    TYPED_SCHEMA = "typed_schema"
    ROUTER_VALIDATION = "router_validation"


class GeminiParserStage(StrEnum):
    """Content-free parser progress marker for safe diagnostics."""

    NOT_STARTED = "not_started"
    HTTP_STATUS = "http_status"
    ENVELOPE = "envelope"
    CANDIDATES = "candidates"
    JSON_EXTRACTION = "json_extraction"
    SAFETY = "safety"
    TYPED_SCHEMA = "typed_schema"
    COMPLETE = "complete"


class GeminiSafeDiagnostic(AuraBaseModel):
    """Bounded diagnostics that cannot contain request or response content."""

    safe_error_code: str = Field(min_length=1, max_length=100)
    validation_stage: GeminiValidationStage
    http_status: int | None = Field(default=None, ge=100, le=599)
    parser_stage: GeminiParserStage = GeminiParserStage.NOT_STARTED
    transport_completed: bool = False
    candidates_found: bool | None = None
    schema_validation_started: bool = False


class GeminiRequest(AuraBaseModel):
    """Transient request passed only across the injected transport boundary."""

    request_id: UUID = Field(default_factory=uuid4)
    capability: ProviderCapability
    model: str = Field(min_length=1, max_length=150)
    system_instruction: str = Field(min_length=1, max_length=5000)
    user_prompt: str = Field(min_length=1, max_length=30000)
    response_schema: dict[str, Any]
    temperature: float = Field(ge=0, le=2)
    top_p: float = Field(gt=0, le=1)
    maximum_output_tokens: int = Field(ge=1, le=65536)
    safety_settings: list[dict[str, str]] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
    founder_smoke_test_diagnostics: bool = False
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at")
    @classmethod
    def created_at_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Gemini request timestamps must be timezone-aware.")
        return value


class GeminiTransportResponse(AuraBaseModel):
    """Raw response confined to the transport and parser boundary."""

    request_id: UUID
    status_code: int = Field(ge=100, le=599)
    response_body: str = Field(max_length=2_000_000)
    latency_ms: float = Field(ge=0)
    provider_request_id: str | None = Field(default=None, max_length=250)
    input_token_count: int | None = Field(default=None, ge=0)
    output_token_count: int | None = Field(default=None, ge=0)
    finish_reason: str | None = Field(default=None, max_length=100)
    safety_metadata: dict[str, Any] = Field(default_factory=dict)
    safe_error_code: str | None = Field(default=None, max_length=100)
    received_at: datetime = Field(default_factory=utc_now)

    @field_validator("received_at")
    @classmethod
    def received_at_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Gemini response timestamps must be timezone-aware.")
        return value


class GeminiSafetyResult(AuraBaseModel):
    allowed: bool
    refusal_reason: str | None = Field(default=None, max_length=500)
    findings: list[str] = Field(default_factory=list)


class GeminiValidatedResponse(AuraBaseModel):
    """Validated Gemini result; raw prompts and responses are excluded."""

    request_id: UUID
    capability: ProviderCapability
    typed_payload: ProviderOutput
    usage: ProviderUsage
    safety_result: GeminiSafetyResult
    validation_warnings: list[str] = Field(default_factory=list)
    fallback_used: bool = False
    completed_at: datetime = Field(default_factory=utc_now)

    @field_validator("completed_at")
    @classmethod
    def completed_at_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Gemini completion timestamps must be timezone-aware.")
        return value
