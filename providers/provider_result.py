"""Generic typed result envelope shared by AI providers."""

from __future__ import annotations

from typing import Generic, TypeVar
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from core import AuraBaseModel
from providers.usage import ProviderUsage


OutputT = TypeVar("OutputT", bound=AuraBaseModel)


class ProviderResult(AuraBaseModel, Generic[OutputT]):
    request_id: UUID = Field(default_factory=uuid4)
    provider: str = Field(min_length=1, max_length=100)
    model: str | None = Field(default=None, max_length=150)
    output: OutputT
    usage: ProviderUsage
    fallback_used: bool = False
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def request_ids_match(self) -> "ProviderResult[OutputT]":
        if self.request_id != self.usage.request_id:
            raise ValueError("Provider result and usage request IDs must match.")
        return self
