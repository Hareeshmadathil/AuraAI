"""Replaceable checkpoint-writing contract preserving Mission Control authority."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from mission_control.models import (
    CheckpointKind,
    CheckpointResumability,
    TaskCheckpoint,
)


class CheckpointWriter(Protocol):
    """Interface future workers can adopt without repository access."""

    def create_checkpoint(
        self,
        *,
        attempt_id: UUID,
        kind: CheckpointKind,
        payload: dict[str, object],
        producer_employee_id: UUID,
        resumability: CheckpointResumability,
        artifact_reference: str | None = None,
        schema_version: int = 1,
        expected_hash: str | None = None,
    ) -> TaskCheckpoint: ...
