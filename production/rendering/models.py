"""Typed models for AuraAI Production v2 local review rendering."""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from core import AuraBaseModel, utc_now


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class RenderArtifactType(StrEnum):
    """Locally exported artifact categories."""

    VOICEOVER_AUDIO = "voiceover_audio"
    SCENE_VIDEO = "scene_video"
    LONG_FORM_VIDEO = "long_form_video"
    SHORT_FORM_VIDEO = "short_form_video"
    THUMBNAIL = "thumbnail"
    SUBTITLE_SRT = "subtitle_srt"
    SUBTITLE_VTT = "subtitle_vtt"
    RENDER_MANIFEST = "render_manifest"
    CHECKSUM_MANIFEST = "checksum_manifest"
    PREVIEW_IMAGE = "preview_image"


class RenderStatus(StrEnum):
    """Lifecycle states for rendering stages and exports."""

    PENDING = "pending"
    RENDERING = "rendering"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    REVIEW_REQUIRED = "review_required"


class RenderEngine(StrEnum):
    """Offline engines used by the local pilot."""

    FFMPEG = "ffmpeg"
    WINDOWS_SAPI = "windows_sapi"
    SILENT_FALLBACK = "silent_fallback"
    DETERMINISTIC_GRAPHICS = "deterministic_graphics"


class RenderCapability(AuraBaseModel):
    """One explicitly detected local rendering capability."""

    capability_name: str = Field(min_length=1, max_length=100)
    available: bool
    executable_path: str | None = Field(default=None, max_length=2000)
    version: str | None = Field(default=None, max_length=500)
    message: str = Field(min_length=1, max_length=2000)
    checked_at: datetime = Field(default_factory=utc_now)

    @field_validator("checked_at")
    @classmethod
    def validate_checked_at(cls, value: datetime) -> datetime:
        return _aware(value)


class RenderSettings(AuraBaseModel):
    """Explicit safe local render configuration."""

    output_root: Path
    overwrite: bool = False
    keep_intermediate_files: bool = False
    long_form_width: int = Field(default=1280, ge=320, le=3840)
    long_form_height: int = Field(default=720, ge=240, le=2160)
    short_width: int = Field(default=720, ge=240, le=2160)
    short_height: int = Field(default=1280, ge=320, le=3840)
    frame_rate: int = Field(default=24, ge=1, le=60)
    audio_sample_rate: int = Field(default=48_000, ge=8_000, le=192_000)
    video_codec: str = Field(default="libx264", pattern=r"^[a-zA-Z0-9_]+$")
    audio_codec: str = Field(default="aac", pattern=r"^[a-zA-Z0-9_]+$")
    pixel_format: str = Field(default="yuv420p", pattern=r"^[a-zA-Z0-9_]+$")
    subtitle_burn_in: bool = False
    create_sidecar_subtitles: bool = True
    maximum_render_duration_seconds: float = Field(default=60.0, ge=5, le=120)
    sample_data: bool = True
    review_required: bool = True

    @field_validator("output_root")
    @classmethod
    def normalize_output_root(cls, value: Path) -> Path:
        return value.expanduser().resolve()

    @model_validator(mode="after")
    def preserve_review_requirement(self) -> "RenderSettings":
        if not self.review_required:
            raise ValueError("Local render settings must require review.")
        return self


class RenderedArtifact(AuraBaseModel):
    """Metadata for one local, never-published render artifact."""

    artifact_id: UUID = Field(default_factory=uuid4)
    artifact_type: RenderArtifactType
    path: Path
    mime_type: str = Field(min_length=1, max_length=200)
    size_bytes: int = Field(ge=0)
    duration_seconds: float | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    checksum_sha256: str | None = None
    render_status: RenderStatus
    generated_at: datetime = Field(default_factory=utc_now)
    sample_data: bool = True
    published: bool = False
    review_required: bool = True
    source_references: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("path")
    @classmethod
    def normalize_path(cls, value: Path) -> Path:
        return value.expanduser().resolve()

    @field_validator("generated_at")
    @classmethod
    def validate_generated_at(cls, value: datetime) -> datetime:
        return _aware(value)

    @field_validator("checksum_sha256")
    @classmethod
    def validate_checksum(cls, value: str | None) -> str | None:
        if value is not None and not _SHA256_PATTERN.fullmatch(value):
            raise ValueError("checksum_sha256 must be a lowercase SHA-256 string.")
        return value

    @model_validator(mode="after")
    def validate_artifact(self) -> "RenderedArtifact":
        if self.published:
            raise ValueError("Local render artifacts cannot be published.")
        if not self.review_required:
            raise ValueError("Local render artifacts must require review.")
        if self.render_status in {RenderStatus.COMPLETED, RenderStatus.REVIEW_REQUIRED}:
            if not self.path.is_file() or self.size_bytes <= 0:
                raise ValueError("Completed artifacts must exist and be nonempty.")
            if self.path.stat().st_size != self.size_bytes:
                raise ValueError("Artifact size_bytes must match the local file.")
            if self.checksum_sha256 is None:
                raise ValueError("Completed artifacts require a SHA-256 checksum.")
            if self.artifact_type in {
                RenderArtifactType.SCENE_VIDEO,
                RenderArtifactType.LONG_FORM_VIDEO,
                RenderArtifactType.SHORT_FORM_VIDEO,
            } and (
                self.duration_seconds is None
                or self.width is None
                or self.height is None
            ):
                raise ValueError("Completed MP4 artifacts require duration and dimensions.")
        return self


class RenderStageResult(AuraBaseModel):
    """Auditable result for one local rendering stage."""

    stage_name: str = Field(min_length=1, max_length=150)
    success: bool
    status: RenderStatus
    started_at: datetime
    completed_at: datetime
    command_summary: list[str] = Field(default_factory=list)
    artifacts: list[RenderedArtifact] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error_message: str | None = Field(default=None, max_length=5000)

    @field_validator("started_at", "completed_at")
    @classmethod
    def validate_timestamps(cls, value: datetime) -> datetime:
        return _aware(value)


class RenderExportManifest(AuraBaseModel):
    """Complete local-export audit manifest."""

    manifest_id: UUID = Field(default_factory=uuid4)
    production_package_id: UUID
    render_engine: RenderEngine
    settings: RenderSettings
    capabilities: list[RenderCapability]
    artifacts: list[RenderedArtifact] = Field(default_factory=list)
    stage_results: list[RenderStageResult] = Field(default_factory=list)
    overall_status: RenderStatus
    review_required: bool = True
    publish_allowed: bool = False
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None

    @field_validator("created_at", "completed_at")
    @classmethod
    def validate_timestamps(cls, value: datetime | None) -> datetime | None:
        return _aware(value) if value is not None else None

    @model_validator(mode="after")
    def validate_manifest(self) -> "RenderExportManifest":
        if self.publish_allowed:
            raise ValueError("Local render manifests cannot allow publishing.")
        if not self.review_required:
            raise ValueError("Local render manifests must require review.")
        root = self.settings.output_root
        for artifact in self.artifacts:
            if not _is_within(artifact.path, root):
                raise ValueError("Render artifact escapes the configured output root.")
        return self


class LocalRenderResult(AuraBaseModel):
    """Final structured result of the local render/export pilot."""

    production_package_id: UUID
    export_manifest: RenderExportManifest
    long_form_video: RenderedArtifact | None = None
    short_form_videos: list[RenderedArtifact] = Field(default_factory=list)
    thumbnail: RenderedArtifact | None = None
    voiceover: RenderedArtifact | None = None
    subtitles: list[RenderedArtifact] = Field(default_factory=list)
    exported_artifacts: list[RenderedArtifact] = Field(default_factory=list)
    runtime_snapshot: dict[str, Any] | None = None
    dashboard_mode: str = Field(min_length=1, max_length=100)
    completed_at: datetime

    @field_validator("completed_at")
    @classmethod
    def validate_completed_at(cls, value: datetime) -> datetime:
        return _aware(value)


class FFmpegCommandResult(AuraBaseModel):
    """Sanitized subprocess result from a controlled local media command."""

    success: bool
    return_code: int
    command_summary: list[str]
    stdout: str = Field(default="", max_length=20_000)
    stderr: str = Field(default="", max_length=20_000)
    timed_out: bool = False
    error_message: str | None = Field(default=None, max_length=5000)


class MediaProbe(AuraBaseModel):
    """Normalized FFprobe metadata needed for validation."""

    path: Path
    duration_seconds: float = Field(ge=0)
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    video_codec: str | None = None
    audio_codec: str | None = None
    has_video: bool = False
    has_audio: bool = False


class RenderValidationCheck(AuraBaseModel):
    """One local-export validation assertion."""

    name: str = Field(min_length=1, max_length=200)
    passed: bool
    blocking: bool
    message: str = Field(min_length=1, max_length=2000)


class RenderValidationReport(AuraBaseModel):
    """Aggregate render validation result."""

    passed: bool
    checks: list[RenderValidationCheck] = Field(min_length=1)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Render timestamps must be timezone-aware.")
    return value


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False
