"""Gemini-specific safety settings for a future live adapter."""

from enum import StrEnum

import json
import re
from typing import Any

from pydantic import Field

from core import AuraBaseModel
from providers.exceptions import ProviderValidationError
from providers.gemini.models import GeminiSafetyResult


class GeminiSafetyMode(StrEnum):
    STRICT = "strict"
    STANDARD = "standard"


class GeminiSafetyConfig(AuraBaseModel):
    mode: GeminiSafetyMode = GeminiSafetyMode.STRICT
    reject_unstructured_output: bool = True
    blocked_categories: list[str] = Field(
        default_factory=lambda: [
            "HARM_CATEGORY_HARASSMENT",
            "HARM_CATEGORY_HATE_SPEECH",
            "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "HARM_CATEGORY_DANGEROUS_CONTENT",
        ]
    )

    def as_transport_settings(self) -> list[dict[str, str]]:
        threshold = (
            "BLOCK_LOW_AND_ABOVE"
            if self.mode == GeminiSafetyMode.STRICT
            else "BLOCK_MEDIUM_AND_ABOVE"
        )
        return [
            {"category": category, "threshold": threshold}
            for category in self.blocked_categories
        ]


_UNSAFE_RESPONSE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)ignore (?:all |any )?(?:previous|prior) instructions"),
    re.compile(r"(?i)(?:execute|run) (?:this )?(?:shell|command|code)"),
    re.compile(r"(?i)tool_calls?\s*[:=]"),
    re.compile(r"(?i)(?:guaranteed|risk-free) (?:income|revenue|returns?)"),
    re.compile(r"(?i)(?:api[_-]?key|access[_-]?token|password)\s*[:=]"),
    re.compile(r"(?i)authorization\s*:\s*bearer\s+\S+"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"\bsk-[0-9A-Za-z_-]{16,}\b"),
)


class GeminiSafetyValidator:
    """Inspect structured provider data before AuraAI accepts it."""

    def inspect(
        self,
        payload: dict[str, Any],
        *,
        finish_reason: str | None,
        safety_metadata: dict[str, Any],
    ) -> GeminiSafetyResult:
        if (finish_reason or "").upper() in {"SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT"}:
            raise ProviderValidationError("Gemini response was refused for safety.")
        serialized = json.dumps(payload, sort_keys=True)
        for pattern in _UNSAFE_RESPONSE_PATTERNS:
            if pattern.search(serialized):
                raise ProviderValidationError(
                    "Gemini response failed content safety validation."
                )
        blocked = [
            item
            for item in safety_metadata.get("ratings", [])
            if item.get("blocked") is True
        ]
        if blocked:
            raise ProviderValidationError("Gemini response contains blocked content.")
        return GeminiSafetyResult(allowed=True)
