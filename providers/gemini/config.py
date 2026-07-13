"""Explicit Gemini stub configuration with no credential fields."""

from pydantic import Field

from core import AuraBaseModel


class GeminiConfig(AuraBaseModel):
    """Non-secret configuration supplied explicitly by a caller."""

    enabled: bool = False
    model: str = Field(default="gemini-stub", min_length=1, max_length=150)
    timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    maximum_output_tokens: int = Field(default=2048, ge=1, le=65536)
