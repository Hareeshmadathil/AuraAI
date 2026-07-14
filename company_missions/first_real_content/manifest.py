"""Checksum manifest models for explicit mission exports."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from core import AuraBaseModel, utc_now


class ArtifactManifestEntry(AuraBaseModel):
    relative_path: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class ArtifactManifest(AuraBaseModel):
    mission_id: UUID
    artifacts: list[ArtifactManifestEntry] = Field(default_factory=list)
    rendered: bool = False
    published: bool = False
    created_at: datetime = Field(default_factory=utc_now)
