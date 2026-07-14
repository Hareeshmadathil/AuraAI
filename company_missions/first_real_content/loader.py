"""Path-safe UTF-8 loading for founder mission specifications."""

from __future__ import annotations

import json
from pathlib import Path

from core import ValidationError

from company_missions.first_real_content.models import FirstContentMissionInput


class FounderInputLoader:
    """Load only explicit JSON files inside an injected input root."""

    def __init__(self, input_root: Path) -> None:
        self._root = input_root.resolve()

    def load(self, path: Path) -> FirstContentMissionInput:
        target = path.resolve() if path.is_absolute() else (self._root / path).resolve()
        try:
            target.relative_to(self._root)
        except ValueError as error:
            raise ValidationError(
                "Founder input must remain inside the configured input root.",
                error_code="UNSAFE_FOUNDER_INPUT_PATH",
            ) from error
        if target.suffix.lower() != ".json" or not target.is_file():
            raise ValidationError(
                "Founder input must be an existing JSON file.",
                error_code="INVALID_FOUNDER_INPUT_FILE",
            )
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
            return FirstContentMissionInput.model_validate(payload)
        except (UnicodeError, json.JSONDecodeError, ValueError) as error:
            raise ValidationError(
                "Founder input failed safe validation.",
                error_code="INVALID_FOUNDER_INPUT",
            ) from error
