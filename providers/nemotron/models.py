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
