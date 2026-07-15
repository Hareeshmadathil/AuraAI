"""Strongly typed models for founder-controlled private video production."""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from core import AuraBaseModel, utc_now


SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class PrivateVideoStatus(StrEnum):
    """Safe lifecycle labels for private production."""

    PREPARING = "preparing"
    BLOCKED = "blocked"
    READY = "ready"
    RENDERING = "rendering"
    REVIEW_REQUIRED = "review_required"
    FAILED = "failed"


class VisualType(StrEnum):
    """Supported evidence-aware visual treatments."""

    SCREEN_RECORDING = "screen_recording"
    SCREENSHOT = "screenshot"
    MOTION_GRAPHIC = "motion_graphic"
    DIAGRAM = "diagram"
    TYPOGRAPHY = "typography"
    FOUNDER_IMAGE = "founder_image"
    PLACEHOLDER = "placeholder"


class AssetType(StrEnum):
    """Private production asset categories."""

    VIDEO = "video"
    IMAGE = "image"
    AUDIO = "audio"
    LOGO = "logo"
    DIAGRAM = "diagram"


class ReviewDecision(StrEnum):
    """Private draft review outcomes; publishing is deliberately absent."""

    PENDING = "pending"
    APPROVE_PRIVATE_DRAFT = "approve_private_draft"
    REQUEST_EDIT = "request_edit"
    REJECT_PRIVATE_DRAFT = "reject_private_draft"


class PrivateVideoProductionInput(AuraBaseModel):
    """Validated source package and founder-controlled output settings."""

    mission_package: Path
    output_root: Path
    mission_id: UUID
    script_artifact_id: UUID
    script_version: int = Field(ge=2)
    script_parent_artifact_id: UUID
    script_content_hash: str
    quality_score: float = Field(ge=0, le=100)
    quality_gate: str
    blocker_count: int = Field(ge=0)
    founder_review_pending: bool
    rendered: bool = False
    published: bool = False
    title: str = Field(min_length=1, max_length=300)
    hook: str = Field(min_length=1, max_length=2000)
    sections: list[str] = Field(min_length=1)
    estimated_duration_seconds: float = Field(gt=0, le=7200)
    source_subtitles: list[dict[str, object]] = Field(default_factory=list)
    version: int = Field(default=1, ge=1)
    loaded_at: datetime = Field(default_factory=utc_now)

    @field_validator("script_content_hash")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not SHA256_PATTERN.fullmatch(value):
            raise ValueError("script_content_hash must be lowercase SHA-256.")
        return value

    @field_validator("loaded_at")
    @classmethod
    def validate_loaded_at(cls, value: datetime) -> datetime:
        return aware_datetime(value)

    @model_validator(mode="after")
    def preserve_source_safety(self) -> "PrivateVideoProductionInput":
        if self.rendered or self.published:
            raise ValueError("Private production requires an unrendered, unpublished source.")
        if self.quality_gate != "passed" or self.blocker_count:
            raise ValueError("A passing blocker-free quality package is required.")
        if not self.founder_review_pending:
            raise ValueError("The source mission must remain pending founder review.")
        return self


class PrivateVideoApproval(AuraBaseModel):
    """Content-bound founder approval with three independent boundaries."""

    approval_id: UUID = Field(default_factory=uuid4)
    mission_id: UUID
    script_artifact_id: UUID
    script_version: int = Field(ge=1)
    content_approved: bool = False
    private_render_approved: bool = False
    publishing_approved: bool = False
    founder_notes: str = Field(default="", max_length=3000)
    approved_at: datetime = Field(default_factory=utc_now)
    approver_role: str = Field(default="Founder", pattern=r"^Founder$")
    content_hash: str
    version: int = Field(default=1, ge=1)

    @field_validator("content_hash")
    @classmethod
    def validate_content_hash(cls, value: str) -> str:
        if not SHA256_PATTERN.fullmatch(value):
            raise ValueError("content_hash must be lowercase SHA-256.")
        return value

    @field_validator("approved_at")
    @classmethod
    def validate_approved_at(cls, value: datetime) -> datetime:
        return aware_datetime(value)

    @model_validator(mode="after")
    def validate_boundaries(self) -> "PrivateVideoApproval":
        if self.publishing_approved:
            raise ValueError("Publishing approval is unavailable in this milestone.")
        if self.private_render_approved and not self.content_approved:
            raise ValueError("Private render approval requires content approval.")
        return self


class NarrationSegment(AuraBaseModel):
    """One normalized, independently synthesized narration section."""

    segment_id: str = Field(min_length=1, max_length=100)
    sequence: int = Field(ge=1)
    heading: str = Field(min_length=1, max_length=300)
    text: str = Field(min_length=1, max_length=20_000)
    pause_after_ms: int = Field(default=450, ge=0, le=5000)
    expected_duration_seconds: float = Field(gt=0, le=600)


class VoiceProfile(AuraBaseModel):
    """Safe metadata for one installed, non-cloned local voice."""

    name: str = Field(min_length=1, max_length=200)
    culture: str = Field(min_length=2, max_length=30)
    gender: str | None = Field(default=None, max_length=30)
    rate: int = Field(default=0, ge=-10, le=10)
    available: bool = True
    provider: str = Field(default="windows_sapi", pattern=r"^windows_sapi$")
    cloned: bool = False

    @model_validator(mode="after")
    def prohibit_cloning(self) -> "VoiceProfile":
        if self.cloned:
            raise ValueError("Cloned or impersonated voices are prohibited.")
        return self


class VoiceSynthesisRequest(AuraBaseModel):
    """Explicit local synthesis request bound to approved content."""

    request_id: UUID = Field(default_factory=uuid4)
    mission_id: UUID
    voice: VoiceProfile
    segments: list[NarrationSegment] = Field(min_length=1)
    output_relative_path: Path
    audition: bool = False
    sample_rate: int = Field(default=48_000, ge=8_000, le=96_000)
    pronunciation_overrides: dict[str, str] = Field(default_factory=dict)

    @field_validator("output_relative_path")
    @classmethod
    def validate_output_path(cls, value: Path) -> Path:
        return safe_relative_path(value, {".wav"})


class VoiceSynthesisResult(AuraBaseModel):
    """Safe result metadata; never contains provider payloads."""

    request_id: UUID
    success: bool
    available: bool
    voice_name: str | None = None
    output_relative_path: Path | None = None
    duration_seconds: float | None = Field(default=None, gt=0)
    sample_rate: int | None = Field(default=None, ge=8000)
    channels: int | None = Field(default=None, ge=1, le=2)
    content_hash: str | None = None
    chunks_created: int = Field(default=0, ge=0)
    message: str = Field(min_length=1, max_length=1000)
    completed_at: datetime = Field(default_factory=utc_now)

    @field_validator("output_relative_path")
    @classmethod
    def validate_optional_path(cls, value: Path | None) -> Path | None:
        return safe_relative_path(value, {".wav"}) if value is not None else None

    @field_validator("content_hash")
    @classmethod
    def validate_voice_hash(cls, value: str | None) -> str | None:
        if value is not None and not SHA256_PATTERN.fullmatch(value):
            raise ValueError("Voice content hash must be lowercase SHA-256.")
        return value

    @field_validator("completed_at")
    @classmethod
    def validate_completed_at(cls, value: datetime) -> datetime:
        return aware_datetime(value)


class SceneEvidenceReference(AuraBaseModel):
    """Traceable evidence expected for a scene."""

    reference_id: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=1000)
    source_relative_path: Path | None = None
    verified: bool = False

    @field_validator("source_relative_path")
    @classmethod
    def validate_source_path(cls, value: Path | None) -> Path | None:
        return safe_relative_path(value) if value is not None else None


class SceneVisual(AuraBaseModel):
    """Purpose-led visual direction for one short scene."""

    visual_type: VisualType
    purpose: str = Field(min_length=1, max_length=1000)
    on_screen_text: str = Field(default="", max_length=300)
    camera_instruction: str = Field(min_length=1, max_length=500)
    transition: str = Field(min_length=1, max_length=100)
    placeholder_watermark: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def label_placeholders(self) -> "SceneVisual":
        if self.visual_type == VisualType.PLACEHOLDER and (
            self.placeholder_watermark != "INTERNAL DRAFT — PLACEHOLDER"
        ):
            raise ValueError("Placeholder scenes require the internal draft watermark.")
        return self


class ScenePlan(AuraBaseModel):
    """One timed scene tied to narration and evidence."""

    scene_id: str = Field(min_length=1, max_length=100)
    narration_segment_id: str = Field(min_length=1, max_length=100)
    expected_start_seconds: float = Field(ge=0)
    expected_end_seconds: float = Field(gt=0)
    visual: SceneVisual
    required_asset_ids: list[str] = Field(default_factory=list)
    evidence_references: list[SceneEvidenceReference] = Field(default_factory=list)
    fallback_visual: str = Field(min_length=1, max_length=500)
    founder_capture_required: bool = False
    accessibility_notes: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_duration(self) -> "ScenePlan":
        if self.expected_end_seconds <= self.expected_start_seconds:
            raise ValueError("Scene end must follow scene start.")
        return self


class AssetRequirement(AuraBaseModel):
    """Founder-supplied asset needed by one or more scenes."""

    asset_id: str = Field(min_length=1, max_length=120)
    asset_type: AssetType
    description: str = Field(min_length=1, max_length=1000)
    target_relative_path: Path
    scene_ids: list[str] = Field(min_length=1)
    expected_duration_seconds: float | None = Field(default=None, gt=0, le=300)
    recommended_width: int = Field(default=1920, ge=320, le=3840)
    recommended_height: int = Field(default=1080, ge=240, le=2160)
    frame_rate: int | None = Field(default=30, ge=1, le=60)
    capture_instructions: str = Field(min_length=1, max_length=2000)
    privacy_notes: list[str] = Field(default_factory=list)

    @field_validator("target_relative_path")
    @classmethod
    def validate_target(cls, value: Path) -> Path:
        return safe_relative_path(value)


class AssetRecord(AuraBaseModel):
    """Validated founder or generated asset metadata."""

    asset_id: str = Field(min_length=1, max_length=120)
    asset_type: AssetType
    relative_path: Path
    supplied: bool
    placeholder: bool = False
    content_hash: str | None = None
    license_note: str | None = Field(default=None, max_length=1000)

    @field_validator("relative_path")
    @classmethod
    def validate_path(cls, value: Path) -> Path:
        return safe_relative_path(value)

    @field_validator("content_hash")
    @classmethod
    def validate_asset_hash(cls, value: str | None) -> str | None:
        if value is not None and not SHA256_PATTERN.fullmatch(value):
            raise ValueError("Asset hash must be lowercase SHA-256.")
        return value


class AssetValidationResult(AuraBaseModel):
    """Aggregate safe asset readiness report."""

    valid: bool
    supplied_asset_ids: list[str] = Field(default_factory=list)
    missing_asset_ids: list[str] = Field(default_factory=list)
    duplicate_asset_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SubtitleCue(AuraBaseModel):
    """Mobile-readable timed subtitle cue."""

    cue_id: str = Field(min_length=1, max_length=100)
    sequence: int = Field(ge=1)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    text: str = Field(min_length=1, max_length=100)
    characters_per_second: float = Field(gt=0, le=20)

    @model_validator(mode="after")
    def validate_readability(self) -> "SubtitleCue":
        if self.end_seconds <= self.start_seconds:
            raise ValueError("Subtitle cue end must follow start.")
        lines = self.text.splitlines()
        if len(lines) > 2 or any(len(line) > 42 for line in lines):
            raise ValueError("Subtitles allow at most two 42-character lines.")
        return self


class TimelineClip(AuraBaseModel):
    """One deterministic clip placed on a timeline track."""

    clip_id: str = Field(min_length=1, max_length=120)
    source_relative_path: Path | None = None
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    placeholder: bool = False
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("source_relative_path")
    @classmethod
    def validate_clip_path(cls, value: Path | None) -> Path | None:
        return safe_relative_path(value) if value is not None else None


class TimelineTrack(AuraBaseModel):
    """Ordered video, narration, music, SFX, or subtitle track."""

    track_id: str = Field(min_length=1, max_length=100)
    kind: str = Field(pattern=r"^(video|narration|music|sfx|subtitles)$")
    clips: list[TimelineClip] = Field(default_factory=list)


class TimelineTransition(AuraBaseModel):
    """Bounded transition between adjacent scenes."""

    from_clip_id: str
    to_clip_id: str
    kind: str = Field(default="fade", max_length=50)
    duration_seconds: float = Field(default=0.35, ge=0, le=2)


class TimelineMarker(AuraBaseModel):
    """Evidence, placeholder, boundary, or review marker."""

    marker_id: str
    at_seconds: float = Field(ge=0)
    kind: str = Field(pattern=r"^(scene|evidence|placeholder|founder_review)$")
    label: str = Field(min_length=1, max_length=300)


class AudioMixPlan(AuraBaseModel):
    """Narration-first audio plan with optional licensed inputs."""

    narration_relative_path: Path | None = None
    music_relative_path: Path | None = None
    sfx_relative_paths: list[Path] = Field(default_factory=list)
    narration_lufs: float = Field(default=-16, ge=-24, le=-10)
    music_gain_db: float = Field(default=-24, ge=-40, le=-12)
    ducking_enabled: bool = True
    fade_in_seconds: float = Field(default=1.0, ge=0, le=10)
    fade_out_seconds: float = Field(default=1.5, ge=0, le=10)
    music_license_note: str | None = Field(default=None, max_length=1000)

    @field_validator("narration_relative_path", "music_relative_path")
    @classmethod
    def validate_audio_path(cls, value: Path | None) -> Path | None:
        return safe_relative_path(value) if value is not None else None

    @field_validator("sfx_relative_paths")
    @classmethod
    def validate_sfx_paths(cls, values: list[Path]) -> list[Path]:
        return [safe_relative_path(value) for value in values]

    @model_validator(mode="after")
    def require_music_license(self) -> "AudioMixPlan":
        if self.music_relative_path is not None and not self.music_license_note:
            raise ValueError("Founder-supplied music requires license metadata.")
        return self


class RenderSpecification(AuraBaseModel):
    """Safe private MP4 specification for modest local hardware."""

    width: int = Field(default=1920, ge=640, le=1920)
    height: int = Field(default=1080, ge=360, le=1080)
    frame_rate: int = Field(default=30, ge=1, le=30)
    video_codec: str = Field(default="libx264", pattern=r"^libx264$")
    audio_codec: str = Field(default="aac", pattern=r"^aac$")
    pixel_format: str = Field(default="yuv420p", pattern=r"^yuv420p$")
    container: str = Field(default="mp4", pattern=r"^mp4$")
    crf: int = Field(default=23, ge=18, le=32)
    preset: str = Field(default="veryfast", pattern=r"^(ultrafast|veryfast|faster)$")
    output_relative_path: Path = Path("render/AuraAI_Mission_Zero_PRIVATE_DRAFT_v1.mp4")
    preview: bool = False
    watermark: str = "INTERNAL REVIEW — NOT FOR PUBLICATION"

    @field_validator("output_relative_path")
    @classmethod
    def validate_mp4_path(cls, value: Path) -> Path:
        value = safe_relative_path(value, {".mp4"})
        if "final" in value.name.lower():
            raise ValueError("Private draft filenames cannot contain 'final'.")
        return value


class RenderManifest(AuraBaseModel):
    """Inspectible FFmpeg plan for a private, never-published draft."""

    manifest_id: UUID = Field(default_factory=uuid4)
    mission_id: UUID
    specification: RenderSpecification
    scene_relative_paths: list[Path] = Field(default_factory=list)
    narration_relative_path: Path | None = None
    subtitle_relative_path: Path | None = None
    expected_duration_seconds: float = Field(gt=0)
    command_summary: list[str] = Field(default_factory=list)
    missing_asset_ids: list[str] = Field(default_factory=list)
    placeholder_count: int = Field(default=0, ge=0)
    publishing_allowed: bool = False
    version: int = Field(default=1, ge=1)

    @field_validator("scene_relative_paths")
    @classmethod
    def validate_scene_paths(cls, values: list[Path]) -> list[Path]:
        return [safe_relative_path(value, {".mp4"}) for value in values]

    @field_validator("narration_relative_path")
    @classmethod
    def validate_narration_path(cls, value: Path | None) -> Path | None:
        return safe_relative_path(value, {".wav"}) if value is not None else None

    @field_validator("subtitle_relative_path")
    @classmethod
    def validate_subtitle_path(cls, value: Path | None) -> Path | None:
        return safe_relative_path(value, {".srt"}) if value is not None else None

    @model_validator(mode="after")
    def forbid_publishing(self) -> "RenderManifest":
        if self.publishing_allowed:
            raise ValueError("Private render manifests cannot allow publishing.")
        return self


class RenderResult(AuraBaseModel):
    """Verified-or-blocked private render result."""

    manifest_id: UUID
    status: PrivateVideoStatus
    output_relative_path: Path | None = None
    size_bytes: int = Field(default=0, ge=0)
    duration_seconds: float | None = Field(default=None, gt=0)
    video_codec: str | None = None
    audio_codec: str | None = None
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    frame_rate: float | None = Field(default=None, gt=0)
    checksum_sha256: str | None = None
    verified: bool = False
    published: bool = False
    warnings: list[str] = Field(default_factory=list)
    completed_at: datetime = Field(default_factory=utc_now)

    @field_validator("output_relative_path")
    @classmethod
    def validate_render_path(cls, value: Path | None) -> Path | None:
        return safe_relative_path(value, {".mp4"}) if value is not None else None

    @field_validator("checksum_sha256")
    @classmethod
    def validate_render_hash(cls, value: str | None) -> str | None:
        if value is not None and not SHA256_PATTERN.fullmatch(value):
            raise ValueError("Render checksum must be lowercase SHA-256.")
        return value

    @field_validator("completed_at")
    @classmethod
    def validate_render_completed_at(cls, value: datetime) -> datetime:
        return aware_datetime(value)

    @model_validator(mode="after")
    def preserve_private_state(self) -> "RenderResult":
        if self.published:
            raise ValueError("Private renders cannot be published.")
        return self


class PrivateVideoReview(AuraBaseModel):
    """Founder review of a private draft, with no publishing decision."""

    review_id: UUID = Field(default_factory=uuid4)
    mission_id: UUID
    render_manifest_id: UUID
    decision: ReviewDecision = ReviewDecision.PENDING
    checklist: dict[str, bool] = Field(default_factory=dict)
    notes: str = Field(default="", max_length=5000)
    placeholder_count: int = Field(default=0, ge=0)
    publishing_approved: bool = False
    reviewed_at: datetime | None = None

    @field_validator("reviewed_at")
    @classmethod
    def validate_reviewed_at(cls, value: datetime | None) -> datetime | None:
        return aware_datetime(value) if value is not None else None

    @model_validator(mode="after")
    def reject_publish_approval(self) -> "PrivateVideoReview":
        if self.publishing_approved:
            raise ValueError("Private video review cannot approve publishing.")
        return self


class PrivateVideoProductionResult(AuraBaseModel):
    """Cumulative safe state for planning, rendering, and private review."""

    production_input: PrivateVideoProductionInput
    approval: PrivateVideoApproval | None = None
    selected_voice: VoiceProfile | None = None
    voice_result: VoiceSynthesisResult | None = None
    scenes: list[ScenePlan] = Field(default_factory=list)
    asset_requirements: list[AssetRequirement] = Field(default_factory=list)
    asset_validation: AssetValidationResult | None = None
    subtitles: list[SubtitleCue] = Field(default_factory=list)
    timeline_tracks: list[TimelineTrack] = Field(default_factory=list)
    transitions: list[TimelineTransition] = Field(default_factory=list)
    markers: list[TimelineMarker] = Field(default_factory=list)
    audio_mix: AudioMixPlan = Field(default_factory=AudioMixPlan)
    render_manifest: RenderManifest | None = None
    render_result: RenderResult | None = None
    review: PrivateVideoReview | None = None
    status: PrivateVideoStatus = PrivateVideoStatus.PREPARING
    runtime_events: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at", "updated_at")
    @classmethod
    def validate_result_timestamps(cls, value: datetime) -> datetime:
        return aware_datetime(value)


def safe_relative_path(value: Path, extensions: set[str] | None = None) -> Path:
    """Validate a portable output-root-relative path."""

    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("Path must remain relative to its configured safe root.")
    if extensions is not None and path.suffix.lower() not in extensions:
        raise ValueError("Path extension is not supported for this artifact.")
    return path


def aware_datetime(value: datetime) -> datetime:
    """Reject naive timestamps in serialized production state."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Private video timestamps must be timezone-aware.")
    return value
