"""Strict JSON-to-Pydantic parsing for future Gemini responses."""

from __future__ import annotations

import json
from typing import TypeVar

from core import AuraBaseModel
from providers.exceptions import ProviderValidationError


ModelT = TypeVar("ModelT", bound=AuraBaseModel)


class GeminiResponseParser:
    def parse(self, payload: str, model_type: type[ModelT]) -> ModelT:
        try:
            decoded = json.loads(payload)
            if not isinstance(decoded, dict):
                raise ValueError("Provider JSON root must be an object.")
            return model_type.model_validate(decoded)
        except (ValueError, TypeError) as error:
            raise ProviderValidationError(
                "Gemini stub response failed JSON or typed validation.",
                provider_name="gemini",
            ) from error
