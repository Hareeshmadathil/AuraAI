"""Offline no-op provider used to demonstrate dependency contracts."""

from __future__ import annotations

from typing import Any

from production.providers.base import (
    ImageGenerationProvider,
    MusicProvider,
    ProviderPlanResult,
    RenderProvider,
    ScriptGenerationProvider,
    VideoGenerationProvider,
    VoiceGenerationProvider,
)


class DeterministicPlanningProvider(
    ScriptGenerationProvider,
    VoiceGenerationProvider,
    ImageGenerationProvider,
    VideoGenerationProvider,
    MusicProvider,
    RenderProvider,
):
    """Return explicit planning metadata and never generate an asset."""

    def plan(self, input_data: dict[str, Any]) -> ProviderPlanResult:
        return ProviderPlanResult(
            provider="deterministic_offline_planner",
            status="not_generated",
            output={"received_keys": sorted(input_data)},
            message="Planning only; no media, audio, image, music, or render was generated.",
        )
