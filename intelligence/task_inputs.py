"""Shared structured input validation for Intelligence employees."""

from __future__ import annotations

from core import TaskRecord, ValidationError


def require_niche(task: TaskRecord) -> str:
    """Return a normalized niche from a task or raise a typed error."""

    value = task.input_data.get("niche")
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("Intelligence tasks require a nonempty niche.")
    return " ".join(value.split())
