"""Validation helpers for Creative Quality employee task inputs."""

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
    """Return a validated typed task input or raise a safe domain error."""

    value = input_data.get(key)
    if isinstance(value, model_type):
        return value
    if isinstance(value, dict):
        try:
            return model_type.model_validate(value)
        except Exception as error:
            raise ValidationError(
                f"Creative Quality task input '{key}' is invalid.",
                details={"exception_type": error.__class__.__name__},
            ) from error
    raise ValidationError(
        f"Creative Quality task requires '{key}' input.",
        details={"required_key": key},
    )
