"""Explicit safe artifact persistence for production plans."""

from __future__ import annotations

import json
import re
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field

from core import AuraBaseModel, StorageError, ValidationError, utc_now


class ArtifactKind(StrEnum):
    """Serializable artifact formats supported by the store."""

    JSON = "json"
    TEXT = "text"
    SRT = "srt"
    VTT = "vtt"


class ArtifactReference(AuraBaseModel):
    """Safe reference to a stored in-memory or filesystem artifact."""

    artifact_id: UUID = Field(default_factory=uuid4)
    name: str
    kind: ArtifactKind
    location: str
    byte_count: int = Field(ge=0)
    in_memory: bool
    created_at: Any = Field(default_factory=utc_now)


class ArtifactStore:
    """Persist artifacts only when an explicit save method is called."""

    def __init__(self, root_directory: Path | None = None, *, in_memory: bool = False) -> None:
        if not in_memory and root_directory is None:
            raise ValidationError("A root directory is required outside in-memory mode.")
        self._root = root_directory.resolve() if root_directory is not None else None
        self._in_memory = in_memory
        self._values: dict[str, bytes] = {}
        self._references: list[ArtifactReference] = []

    def save_model(
        self,
        name: str,
        model: Any,
        *,
        overwrite: bool = False,
    ) -> ArtifactReference:
        """Serialize a Pydantic model or JSON-compatible value explicitly."""

        value = model.model_dump(mode="json") if hasattr(model, "model_dump") else model
        text = json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True)
        return self._save(name, ArtifactKind.JSON, text, overwrite=overwrite)

    def save_script(self, name: str, text: str, *, overwrite: bool = False) -> ArtifactReference:
        return self._save(name, ArtifactKind.TEXT, text, overwrite=overwrite)

    def save_srt(self, name: str, text: str, *, overwrite: bool = False) -> ArtifactReference:
        return self._save(name, ArtifactKind.SRT, text, overwrite=overwrite)

    def save_vtt(self, name: str, text: str, *, overwrite: bool = False) -> ArtifactReference:
        return self._save(name, ArtifactKind.VTT, text, overwrite=overwrite)

    def save_assembly_manifest(self, name: str, model: Any, *, overwrite: bool = False) -> ArtifactReference:
        return self.save_model(name, model, overwrite=overwrite)

    def list_saved_artifacts(self) -> tuple[ArtifactReference, ...]:
        return tuple(self._references)

    def read_memory_artifact(self, reference: ArtifactReference) -> bytes:
        """Read a test-mode artifact without exposing filesystem state."""

        if not reference.in_memory:
            raise ValidationError("The artifact is not stored in memory.")
        key = reference.location.removeprefix("memory://")
        return self._values[key]

    def _save(
        self,
        name: str,
        kind: ArtifactKind,
        text: str,
        *,
        overwrite: bool,
    ) -> ArtifactReference:
        safe_name = self._safe_name(name)
        extension = "txt" if kind == ArtifactKind.TEXT else kind.value
        filename = f"{safe_name}.{extension}"
        payload = text.encode("utf-8")
        if self._in_memory:
            if filename in self._values and not overwrite:
                raise StorageError("Artifact already exists.")
            self._values[filename] = payload
            location = f"memory://{filename}"
        else:
            if self._root is None:
                raise StorageError("Artifact root is unavailable.")
            target = (self._root / filename).resolve()
            if self._root not in target.parents:
                raise ValidationError("Artifact path escapes the configured root.")
            if target.exists() and not overwrite:
                raise StorageError("Artifact already exists.")
            self._root.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(target.suffix + ".tmp")
            temporary.write_bytes(payload)
            temporary.replace(target)
            location = str(target)
        reference = ArtifactReference(
            name=filename,
            kind=kind,
            location=location,
            byte_count=len(payload),
            in_memory=self._in_memory,
        )
        self._references.append(reference)
        return reference

    @staticmethod
    def _safe_name(name: str) -> str:
        if ".." in Path(name).parts or Path(name).is_absolute() or Path(name).name != name:
            raise ValidationError("Artifact names cannot contain path components.")
        clean = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip()).strip("-_.")
        if not clean:
            raise ValidationError("Artifact name is required.")
        return clean[:120]
