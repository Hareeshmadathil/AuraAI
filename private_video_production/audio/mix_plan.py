"""Narration-first audio mix planning."""

from pathlib import Path

from private_video_production.models import AudioMixPlan


def narration_only_mix(narration_path: Path | None = None) -> AudioMixPlan:
    """Return the safe default with no fabricated music or effects."""

    return AudioMixPlan(narration_relative_path=narration_path)
