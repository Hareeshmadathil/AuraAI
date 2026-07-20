"""Decoupled checkpoint and artifact interfaces for deterministic offline rendering."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol
from uuid import UUID

from core import ValidationError
from mission_control.models import ArtifactRecord, TaskCheckpoint
from runtime_engine.artifact_context import (
    ArtifactRegistrar,
    ArtifactResolver,
    IntegrityVerifier,
    DefaultIntegrityVerifier,
    MissionControlArtifactRegistrar,
    MissionControlArtifactResolver,
)


class CheckpointReader(Protocol):
    def get_latest_checkpoint(
        self,
        mission_id: UUID,
        task_id: UUID,
        sequence: int | None = None,
        metadata_filter: dict[str, str] | None = None,
    ) -> TaskCheckpoint | None: ...


class MissionControlCheckpointReader(CheckpointReader):
    def __init__(self, service) -> None:
        self.service = service

    def get_latest_checkpoint(
        self,
        mission_id: UUID,
        task_id: UUID,
        sequence: int | None = None,
        metadata_filter: dict[str, str] | None = None,
    ) -> TaskCheckpoint | None:
        checkpoints = self.service.list_checkpoints(mission_id)
        relevant = [
            cp for cp in checkpoints
            if cp.task_id == task_id
            and (sequence is None or cp.sequence == sequence)
        ]
        if metadata_filter:
            for k, v in metadata_filter.items():
                relevant = [cp for cp in relevant if str(cp.payload.get(k)) == str(v)]
        if not relevant:
            return None
        return max(relevant, key=lambda cp: cp.sequence)
