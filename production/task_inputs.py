"""Shared validation helpers for production employee task inputs."""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from core import ValidationError


ModelT = TypeVar("ModelT", bound=BaseModel)


def require_model(
    input_data: dict[str, Any],
    key: str,
    model_type: type[ModelT],
) -> ModelT:
    """Return one validated model from a task input dictionary."""

    value = input_data.get(key)
    if isinstance(value, model_type):
        return value
    if isinstance(value, dict):
        try:
            return model_type.model_validate(value)
        except Exception as error:
            raise ValidationError(
                f"Production task input '{key}' is invalid.",
                details={"exception_type": error.__class__.__name__},
            ) from error
    raise ValidationError(
        f"Production task requires '{key}' input.",
        details={"required_key": key},
    )


def require_text(input_data: dict[str, Any], key: str) -> str:
    """Return one required non-empty text input."""

    value = input_data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(
            f"Production task requires non-empty '{key}' input.",
            details={"required_key": key},
        )
    return value.strip()
