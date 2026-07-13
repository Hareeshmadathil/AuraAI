"""Shared deterministic graphic-filter helpers for local FFmpeg rendering."""

from __future__ import annotations

from pathlib import Path

from core import ValidationError


def drawtext_filter(text: str) -> str:
    """Return a drawtext prefix using an explicit installed local font."""

    font = _local_font_path()
    escaped = str(font).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
    return f"drawtext=fontfile='{escaped}':text='{text}'"


def _local_font_path() -> Path:
    """Locate a common OS font without network access or hidden state."""

    candidates = (
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise ValidationError("No supported local review font is available.")
