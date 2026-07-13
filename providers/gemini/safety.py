"""Gemini-specific safety settings for a future live adapter."""

from enum import StrEnum

from core import AuraBaseModel


class GeminiSafetyMode(StrEnum):
    STRICT = "strict"
    STANDARD = "standard"


class GeminiSafetyConfig(AuraBaseModel):
    mode: GeminiSafetyMode = GeminiSafetyMode.STRICT
    reject_unstructured_output: bool = True
    allow_network_requests: bool = False
