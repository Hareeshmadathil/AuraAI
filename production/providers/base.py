"""Replaceable provider contracts for future media generation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import Field

from core import AuraBaseModel


class ProviderPlanResult(AuraBaseModel):
    """Provider-neutral result that cannot imply generated media exists."""

    provider: str = Field(min_length=1, max_length=150)
    status: str = Field(pattern="^(planned|mock|not_generated|not_rendered)$")
    output: dict[str, Any] = Field(default_factory=dict)
    message: str = Field(min_length=1, max_length=1000)


class PlanningProvider(ABC):
    """Base interface for an injected future production provider."""

    @abstractmethod
    def plan(self, input_data: dict[str, Any]) -> ProviderPlanResult:
        """Return a structured plan without performing network work."""


class ScriptGenerationProvider(PlanningProvider):
    """Contract for future script generation implementations."""


class VoiceGenerationProvider(PlanningProvider):
    """Contract for future voice generation implementations."""


class ImageGenerationProvider(PlanningProvider):
    """Contract for future image generation implementations."""


class VideoGenerationProvider(PlanningProvider):
    """Contract for future video generation implementations."""


class MusicProvider(PlanningProvider):
    """Contract for future licensed-music implementations."""


class RenderProvider(PlanningProvider):
    """Contract for future rendering implementations."""
