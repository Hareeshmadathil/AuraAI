"""Transport-neutral Nemotron request and response models."""
from __future__ import annotations
from typing import Any
from pydantic import Field
from core import AuraBaseModel
from providers.models import ProviderCapability


class NemotronRequest(AuraBaseModel):
    capability: ProviderCapability
    prompt: str = Field(min_length=1, max_length=30000)
    model: str
    response_schema: dict[str, Any]
    maximum_output_tokens: int
    temperature: float


class NemotronTransportResponse(AuraBaseModel):
    payload: dict[str, Any]
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    latency_ms: float = Field(default=0, ge=0)
    http_status_class: str = Field(default="unknown", pattern=r"^(?:[1-5]xx|unknown)$")
    final_answer_field: str = "payload"
    safe_diagnostics: dict[str, Any] = Field(default_factory=dict)


class NemotronResponseShape(AuraBaseModel):
    """Content-free structural metadata for safe provider diagnostics."""

    top_level_keys: list[str] = Field(default_factory=list)
    choices_count: int = Field(default=0, ge=0)
    message_keys: list[str] = Field(default_factory=list)
    message_value_types: dict[str, str] = Field(default_factory=dict)
    content_kind: str = "missing"
    content_character_count: int = Field(default=0, ge=0)
    reasoning_field_present: bool = False
    reasoning_character_count: int = Field(default=0, ge=0)
    finish_reason: str | None = None
    usage: dict[str, int] = Field(default_factory=dict)
    http_status_class: str = "unknown"
