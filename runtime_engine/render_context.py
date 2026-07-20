"""Decoupled checkpoint and artifact interfaces for deterministic offline rendering."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol
from uuid import UUID

from core import ValidationError
from mission_control.models import ArtifactRecord, TaskCheckpoint


class CheckpointReader(Protocol):
    def get_latest_checkpoint(
        self,
        mission_id: UUID,
        task_id: UUID,
        sequence: int | None = None,
        metadata_filter: dict[str, str] | None = None,
    ) -> TaskCheckpoint | None: ...


class ArtifactRegistrar(Protocol):
    def register_artifact(
        self,
        *,
        mission_id: UUID,
        task_id: UUID,
        artifact_type: str,
        location: str,
        value: object,
        provenance: dict[str, object],
    ) -> ArtifactRecord: ...


class ArtifactResolver(Protocol):
    def resolve_artifact(self, artifact_id: UUID) -> ArtifactRecord | None: ...


class IntegrityVerifier(Protocol):
    def verify(self, artifact_id: UUID, expected_hash: str) -> Path: ...


class DefaultIntegrityVerifier(IntegrityVerifier):
    def __init__(
        self,
        resolver: ArtifactResolver,
        allowed_roots: list[Path],
    ) -> None:
        self.resolver = resolver
        self.allowed_roots = [root.resolve() for root in allowed_roots]

    def verify(self, artifact_id: UUID, expected_hash: str) -> Path:
        record = self.resolver.resolve_artifact(artifact_id)
        if record is None:
            raise ValidationError(f"Unknown artifact: {artifact_id}")

        if record.content_hash != expected_hash:
            raise ValidationError(
                f"Artifact {artifact_id} hash mismatch. "
                f"Expected: {expected_hash}, Actual: {record.content_hash}"
            )

        candidate = Path(record.location).resolve()
        
        # Prevent symlink escapes and traversal
        allowed = any(
            root in candidate.parents or candidate == root
            for root in self.allowed_roots
        )
        if not allowed:
            raise ValidationError("Artifact location is outside allowed roots.")
            
        if not candidate.is_file():
            raise ValidationError("Artifact file does not exist.")
            
        actual_hash = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            raise ValidationError("Artifact contents do not match expected hash.")
            
        return candidate


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


class MissionControlArtifactRegistrar(ArtifactRegistrar):
    def __init__(self, service) -> None:
        self.service = service

    def register_artifact(
        self,
        *,
        mission_id: UUID,
        task_id: UUID,
        artifact_type: str,
        location: str,
        value: object,
        provenance: dict[str, object],
    ) -> ArtifactRecord:
        return self.service.register_artifact(
            mission_id=mission_id,
            task_id=task_id,
            artifact_type=artifact_type,
            location=location,
            value=value,
            provenance=provenance,
        )


class MissionControlArtifactResolver(ArtifactResolver):
    def __init__(self, service) -> None:
        self.service = service

    def resolve_artifact(self, artifact_id: UUID) -> ArtifactRecord | None:
        # Assuming list_artifacts can be used or we add get_artifact
        # Let's search in list_artifacts for now
        for artifact in self.service.list_artifacts():
            if artifact.artifact_id == artifact_id:
                return artifact
        return None
