"""Clearly labelled deterministic SVG placeholders for internal review."""

from __future__ import annotations

from html import escape
from pathlib import Path

from core import ValidationError

from private_video_production.models import AssetRequirement


class PlaceholderFactory:
    """Create branded non-deceptive evidence-needed cards."""

    def __init__(self, output_root: Path) -> None:
        self._root = output_root.resolve()

    def create(self, requirement: AssetRequirement) -> Path:
        target = (self._root / "placeholders" / f"{requirement.asset_id}.svg").resolve()
        try:
            target.relative_to(self._root)
        except ValueError as error:
            raise ValidationError("Placeholder output escapes the configured root.") from error
        target.parent.mkdir(parents=True, exist_ok=True)
        label = escape(requirement.description[:120])
        target.write_text(
            "<svg xmlns='http://www.w3.org/2000/svg' width='1920' height='1080' role='img'>"
            "<rect width='1920' height='1080' fill='#07111f'/><rect width='1920' height='12' fill='#62e6c5'/>"
            f"<text x='960' y='500' fill='white' font-size='54' text-anchor='middle'>{label}</text>"
            "<text x='960' y='620' fill='#f4c875' font-size='30' text-anchor='middle'>"
            "INTERNAL DRAFT — PLACEHOLDER</text></svg>",
            encoding="utf-8",
        )
        return target
