"""Typed domain models for AuraAI's offline production pipeline."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import PurePath
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from core import AuraBaseModel, ContentPlatform, utc_now


SCRIPT_DURATION_TOLERANCE_PERCENT = 15.0


class VideoStyle(StrEnum):
    """Provider-neutral visual styles supported by Production v1."""

    LIVE_ACTION = "live_action"
    CINEMATIC_LIVE_ACTION = "cinematic_live_action"
    ANIME = "anime"
    ANIMATION = "animation"
    MOTION_GRAPHICS = "motion_graphics"
    DOCUMENTARY = "documentary"
    HYBRID = "hybrid"


class VideoFormat(StrEnum):
    """Production output formats independent of delivery providers."""

    YOUTUBE_LONG_FORM = "youtube_long_form"
    YOUTUBE_SHORT = "youtube_short"
    INSTAGRAM_REEL = "instagram_reel"
    TIKTOK_VIDEO = "tiktok_video"


class ProductionStage(StrEnum):
    """Ordered stages in the deterministic production pipeline."""

    BRIEF = "brief"
    SCRIPT = "script"
    STORYBOARD = "storyboard"
    VOICE = "voice"
    VISUAL = "visual"
    THUMBNAIL = "thumbnail"
    SHORT_FORM = "short_form"
    SUBTITLES = "subtitles"
    ASSEMBLY = "assembly"
    QUALITY_CONTROL = "quality_control"
    APPROVAL = "approval"
    COMPLETED = "completed"
    FAILED = "failed"


class AssetType(StrEnum):
    """Artifact and visual-request types created by Production v1."""

    SCRIPT = "script"
    VOICEOVER_PLAN = "voiceover_plan"
    STORYBOARD = "storyboard"
    VISUAL_PROMPT = "visual_prompt"
    THUMBNAIL_CONCEPT = "thumbnail_concept"
    SUBTITLE_FILE = "subtitle_file"
    VIDEO_MANIFEST = "video_manifest"
    SHORT_FORM_SCRIPT = "short_form_script"
    METADATA = "metadata"
    QUALITY_REPORT = "quality_report"


class ApprovalRequirement(StrEnum):
    """Human-governance level associated with an output."""

    NONE = "none"
    AUTOMATED_SAFE = "automated_safe"
    FOUNDER_REQUIRED = "founder_required"


class ProductionApprovalStatus(StrEnum):
    """Approval state for a production package."""

    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class AssetStatus(StrEnum):
    """State of a planned media asset."""

    PLANNED = "planned"
    NOT_GENERATED = "not_generated"


class VisualRequestKind(StrEnum):
    """Planned visual treatment requested for a storyboard scene."""

    IMAGE = "image"
    MOTION_GRAPHIC = "motion_graphic"
    B_ROLL = "b_roll"
    STOCK_PLACEHOLDER = "stock_like_placeholder"
    VIDEO_GENERATION = "video_generation"


class RenderStatus(StrEnum):
    """State of an assembly manifest in this non-rendering milestone."""

    PLANNED = "planned"
    NOT_RENDERED = "not_rendered"


class QualitySeverity(StrEnum):
    """Impact level for a production quality check."""

    INFO = "info"
    WARNING = "warning"
    BLOCKING = "blocking"


class TrackType(StrEnum):
    """Logical assembly tracks described by a video manifest."""

    VIDEO = "video"
    VOICE = "voice"
    MUSIC = "music_placeholder"
    SUBTITLE = "subtitle"
    MOTION_GRAPHICS = "motion_graphics"
    TRANSITION = "transition"


class ProductionInput(AuraBaseModel):
    """Validated strategic and marketing input for one production run."""

    mission_id: UUID | None = None
    brand_name: str = Field(min_length=1, max_length=200)
    topic: str = Field(min_length=1, max_length=500)
    working_title: str = Field(min_length=1, max_length=250)
    target_audience: str = Field(min_length=1, max_length=2000)
    audience_problem: str = Field(min_length=1, max_length=3000)
    audience_promise: str = Field(min_length=1, max_length=3000)
    content_pillars: list[str] = Field(min_length=1)
    primary_platform: ContentPlatform
    preferred_style: VideoStyle | None = None
    target_duration_seconds: float = Field(gt=0, le=14_400)
    language: str = Field(min_length=1, max_length=100)
    tone: str = Field(min_length=1, max_length=500)
    campaign_goal: str = Field(min_length=1, max_length=2000)
    primary_keyword: str = Field(min_length=1, max_length=250)
    secondary_keywords: list[str] = Field(default_factory=list)
    source_notes: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    preferred_call_to_action: str = Field(min_length=1, max_length=1000)
    requires_founder_approval: bool = True
    sample_data: bool = False


class ContentBrief(AuraBaseModel):
    """Creative and factual production direction for one video."""

    brief_id: UUID = Field(default_factory=uuid4)
    production_input: ProductionInput
    selected_style: VideoStyle
    format: VideoFormat
    creative_direction: str = Field(min_length=1, max_length=5000)
    core_message: str = Field(min_length=1, max_length=3000)
    learning_outcomes: list[str] = Field(min_length=1)
    hook_strategy: str = Field(min_length=1, max_length=2000)
    narrative_structure: list[str] = Field(min_length=1)
    evidence_requirements: list[str] = Field(min_length=1)
    prohibited_claims: list[str] = Field(min_length=1)
    monetization_alignment: str = Field(min_length=1, max_length=2000)
    estimated_scene_count: int = Field(ge=1)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        return _aware(value)


class ScriptSection(AuraBaseModel):
    """One timed and visually directed part of a video script."""

    section_id: UUID = Field(default_factory=uuid4)
    section_type: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=250)
    purpose: str = Field(min_length=1, max_length=2000)
    narration: str = Field(min_length=1, max_length=30_000)
    estimated_duration_seconds: float = Field(gt=0)
    visual_intent: str = Field(min_length=1, max_length=3000)
    retention_device: str = Field(min_length=1, max_length=1000)
    source_notes: list[str] = Field(default_factory=list)
    claims_requiring_verification: list[str] = Field(default_factory=list)


class VideoScript(AuraBaseModel):
    """Complete deterministic narration and structure for a video."""

    script_id: UUID = Field(default_factory=uuid4)
    brief_id: UUID
    title: str = Field(min_length=1, max_length=250)
    hook: str = Field(min_length=1, max_length=2000)
    sections: list[ScriptSection] = Field(min_length=1)
    call_to_action: str = Field(min_length=1, max_length=2000)
    total_estimated_duration_seconds: float = Field(gt=0)
    word_count: int = Field(ge=1)
    primary_keyword: str = Field(min_length=1, max_length=250)
    secondary_keywords: list[str] = Field(default_factory=list)
    disclaimer_notes: list[str] = Field(default_factory=list)
    sample_data: bool = False
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        return _aware(value)

    @model_validator(mode="after")
    def validate_sections(self) -> "VideoScript":
        section_total = sum(
            section.estimated_duration_seconds for section in self.sections
        )
        if abs(section_total - self.total_estimated_duration_seconds) > 1.0:
            raise ValueError("Script section durations must match total duration.")
        actual_words = sum(
            len(section.narration.split()) for section in self.sections
        )
        if actual_words != self.word_count:
            raise ValueError("word_count must match the supplied narration.")
        return self


class StoryboardScene(AuraBaseModel):
    """One sequential, timed scene linked to a script section."""

    scene_id: UUID = Field(default_factory=uuid4)
    sequence_number: int = Field(ge=1)
    script_section_id: UUID
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    narration: str = Field(min_length=1, max_length=30_000)
    visual_description: str = Field(min_length=1, max_length=5000)
    style: VideoStyle
    shot_type: str = Field(min_length=1, max_length=250)
    camera_direction: str = Field(min_length=1, max_length=1000)
    on_screen_text: str = Field(default="", max_length=500)
    transition: str = Field(min_length=1, max_length=250)
    visual_prompt: str = Field(min_length=1, max_length=5000)
    negative_prompt: str = Field(min_length=1, max_length=3000)
    source_asset_requirements: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_timing(self) -> "StoryboardScene":
        if self.end_seconds <= self.start_seconds:
            raise ValueError("Scene end time must be after its start time.")
        return self


class Storyboard(AuraBaseModel):
    """Sequential visual plan covering every script section."""

    storyboard_id: UUID = Field(default_factory=uuid4)
    script_id: UUID
    scenes: list[StoryboardScene] = Field(min_length=1)
    total_duration_seconds: float = Field(gt=0)
    style_continuity_notes: list[str] = Field(min_length=1)
    character_continuity_notes: list[str] = Field(min_length=1)
    sample_data: bool = False
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        return _aware(value)

    @model_validator(mode="after")
    def validate_scene_order(self) -> "Storyboard":
        for expected, scene in enumerate(self.scenes, start=1):
            if scene.sequence_number != expected:
                raise ValueError("Storyboard scene numbering must be sequential.")
            if expected > 1 and scene.start_seconds < self.scenes[expected - 2].end_seconds:
                raise ValueError("Storyboard scene times cannot overlap.")
        if abs(self.scenes[-1].end_seconds - self.total_duration_seconds) > 1.0:
            raise ValueError("Storyboard duration must match the final scene.")
        return self


class VoiceProfile(AuraBaseModel):
    """Provider-neutral direction for a future synthesized or human voice."""

    profile_id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=150)
    language: str = Field(min_length=1, max_length=100)
    voice_character: str = Field(min_length=1, max_length=1000)
    pace_words_per_minute: int = Field(gt=0, le=300)
    energy_level: str = Field(min_length=1, max_length=100)
    pronunciation_notes: list[str] = Field(default_factory=list)
    provider_hint: str | None = Field(default=None, max_length=250)
    sample_data: bool = False


class VoiceSegment(AuraBaseModel):
    """Timed voice direction corresponding to one storyboard scene."""

    segment_id: UUID = Field(default_factory=uuid4)
    scene_id: UUID
    text: str = Field(min_length=1, max_length=30_000)
    estimated_duration_seconds: float = Field(gt=0)
    emotion: str = Field(min_length=1, max_length=100)
    emphasis_words: list[str] = Field(default_factory=list)
    pause_after_seconds: float = Field(ge=0, le=10)
    pronunciation_notes: list[str] = Field(default_factory=list)


class VoiceoverPlan(AuraBaseModel):
    """In-memory voice performance plan; it contains no generated audio."""

    plan_id: UUID = Field(default_factory=uuid4)
    script_id: UUID
    profile: VoiceProfile
    segments: list[VoiceSegment] = Field(min_length=1)
    total_duration_seconds: float = Field(gt=0)
    output_format: str = Field(min_length=1, max_length=50)
    sample_data: bool = False
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        return _aware(value)

    @model_validator(mode="after")
    def validate_total_duration(self) -> "VoiceoverPlan":
        total = sum(segment.estimated_duration_seconds for segment in self.segments)
        if abs(total - self.total_duration_seconds) > 1.0:
            raise ValueError("Voice segment durations must match plan duration.")
        return self


class VisualAssetRequest(AuraBaseModel):
    """A planned, not-generated request for a future visual provider."""

    request_id: UUID = Field(default_factory=uuid4)
    scene_id: UUID
    asset_type: AssetType
    request_kind: VisualRequestKind
    style: VideoStyle
    prompt: str = Field(min_length=1, max_length=5000)
    negative_prompt: str = Field(min_length=1, max_length=3000)
    aspect_ratio: str = Field(min_length=3, max_length=20)
    target_duration_seconds: float | None = Field(default=None, gt=0)
    continuity_reference: str | None = Field(default=None, max_length=1000)
    rights_requirements: list[str] = Field(min_length=1)
    status: AssetStatus = AssetStatus.NOT_GENERATED
    output_path: str | None = None
    sample_data: bool = False


class VisualGenerationPlan(AuraBaseModel):
    """Complete provider-neutral visual request plan."""

    plan_id: UUID = Field(default_factory=uuid4)
    storyboard_id: UUID
    requests: list[VisualAssetRequest] = Field(min_length=1)
    estimated_asset_count: int = Field(ge=1)
    consistency_rules: list[str] = Field(min_length=1)
    fallback_asset_strategy: list[str] = Field(min_length=1)
    sample_data: bool = False
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        return _aware(value)

    @model_validator(mode="after")
    def validate_asset_count(self) -> "VisualGenerationPlan":
        if self.estimated_asset_count != len(self.requests):
            raise ValueError("estimated_asset_count must match requests.")
        return self


class ThumbnailConcept(AuraBaseModel):
    """One review-ready thumbnail direction, not a generated image."""

    concept_id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=1, max_length=250)
    concept_name: str = Field(min_length=1, max_length=150)
    visual_composition: str = Field(min_length=1, max_length=2000)
    primary_text: str = Field(min_length=1, max_length=60)
    secondary_text: str | None = Field(default=None, max_length=60)
    emotional_trigger: str = Field(min_length=1, max_length=500)
    subject_focus: str = Field(min_length=1, max_length=1000)
    background_direction: str = Field(min_length=1, max_length=1000)
    contrast_guidance: str = Field(min_length=1, max_length=1000)
    mobile_readability_notes: str = Field(min_length=1, max_length=1000)
    generation_prompt: str = Field(min_length=1, max_length=4000)
    negative_prompt: str = Field(min_length=1, max_length=2000)
    expected_audience_response: str = Field(min_length=1, max_length=1000)
    sample_data: bool = False


class ThumbnailPlan(AuraBaseModel):
    """Three or more thumbnail concepts and a testing recommendation."""

    plan_id: UUID = Field(default_factory=uuid4)
    script_id: UUID
    concepts: list[ThumbnailConcept] = Field(min_length=1)
    recommended_concept_id: UUID
    testing_hypothesis: str = Field(min_length=1, max_length=2000)
    sample_data: bool = False
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        return _aware(value)

    @model_validator(mode="after")
    def validate_recommendation(self) -> "ThumbnailPlan":
        if self.recommended_concept_id not in {
            concept.concept_id for concept in self.concepts
        }:
            raise ValueError("Recommended thumbnail concept must exist.")
        return self


class ShortFormAsset(AuraBaseModel):
    """Standalone platform-adapted short-form concept."""

    asset_id: UUID = Field(default_factory=uuid4)
    source_script_id: UUID
    platform: ContentPlatform
    title: str = Field(min_length=1, max_length=250)
    hook: str = Field(min_length=1, max_length=1000)
    narration: str = Field(min_length=1, max_length=5000)
    selected_scene_ids: list[UUID] = Field(min_length=1)
    target_duration_seconds: float = Field(gt=0, le=180)
    caption: str = Field(min_length=1, max_length=2200)
    hashtags: list[str] = Field(min_length=1)
    call_to_action: str = Field(min_length=1, max_length=1000)
    loop_strategy: str = Field(min_length=1, max_length=1000)
    sample_data: bool = False


class ShortFormPackage(AuraBaseModel):
    """Cross-platform derivatives from one long-form script."""

    package_id: UUID = Field(default_factory=uuid4)
    source_script_id: UUID
    assets: list[ShortFormAsset] = Field(min_length=1)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        return _aware(value)


class SubtitleSegment(AuraBaseModel):
    """One sequential subtitle cue."""

    index: int = Field(ge=1)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    text: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_timing(self) -> "SubtitleSegment":
        if self.end_seconds <= self.start_seconds:
            raise ValueError("Subtitle end time must be after start time.")
        return self


class SubtitlePackage(AuraBaseModel):
    """Validated in-memory SRT and WebVTT subtitle output."""

    package_id: UUID = Field(default_factory=uuid4)
    script_id: UUID
    language: str = Field(min_length=1, max_length=100)
    segments: list[SubtitleSegment] = Field(min_length=1)
    srt_text: str = Field(min_length=1)
    vtt_text: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        return _aware(value)

    @model_validator(mode="after")
    def validate_segments(self) -> "SubtitlePackage":
        for expected, segment in enumerate(self.segments, start=1):
            if segment.index != expected:
                raise ValueError("Subtitle numbering must be sequential.")
            if expected > 1 and segment.start_seconds < self.segments[expected - 2].end_seconds:
                raise ValueError("Subtitle segments cannot overlap.")
        if not self.vtt_text.startswith("WEBVTT"):
            raise ValueError("WebVTT output must start with WEBVTT.")
        return self


class AssemblyTrackItem(AuraBaseModel):
    """One planned item on a logical assembly track."""

    item_id: UUID = Field(default_factory=uuid4)
    track_type: TrackType
    scene_id: UUID | None = None
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    source_reference: str = Field(min_length=1, max_length=1000)
    instructions: str = Field(min_length=1, max_length=3000)
    required: bool = True
    status: AssetStatus = AssetStatus.PLANNED

    @model_validator(mode="after")
    def validate_timing(self) -> "AssemblyTrackItem":
        if self.end_seconds <= self.start_seconds:
            raise ValueError("Assembly track end must be after start.")
        return self


class VideoAssemblyManifest(AuraBaseModel):
    """Review-ready editing manifest; it is not a rendered video."""

    manifest_id: UUID = Field(default_factory=uuid4)
    script_id: UUID
    storyboard_id: UUID
    voiceover_plan_id: UUID
    visual_plan_id: UUID
    format: VideoFormat
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    frame_rate: float = Field(gt=0, le=120)
    audio_sample_rate: int = Field(gt=0)
    duration_seconds: float = Field(gt=0)
    track_items: list[AssemblyTrackItem] = Field(min_length=1)
    subtitle_package_id: UUID
    thumbnail_plan_id: UUID
    output_filename: str = Field(min_length=1, max_length=255)
    output_directory: str = Field(min_length=1, max_length=1000)
    render_status: RenderStatus = RenderStatus.NOT_RENDERED
    sample_data: bool = False
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        return _aware(value)

    @model_validator(mode="after")
    def validate_safe_output(self) -> "VideoAssemblyManifest":
        if PurePath(self.output_filename).name != self.output_filename:
            raise ValueError("output_filename must not contain a path.")
        directory = PurePath(self.output_directory)
        if directory.is_absolute() or ".." in directory.parts:
            raise ValueError("output_directory must be a safe relative path.")
        return self


class QualityCheck(AuraBaseModel):
    """One transparent production quality assertion."""

    check_id: UUID = Field(default_factory=uuid4)
    category: str = Field(min_length=1, max_length=150)
    name: str = Field(min_length=1, max_length=250)
    passed: bool
    severity: QualitySeverity
    message: str = Field(min_length=1, max_length=3000)
    remediation: str | None = Field(default=None, max_length=3000)


class ProductionQualityReport(AuraBaseModel):
    """Aggregate quality and governance result for a package."""

    report_id: UUID = Field(default_factory=uuid4)
    production_package_id: UUID
    checks: list[QualityCheck] = Field(min_length=1)
    passed: bool
    approval_required: ApprovalRequirement
    blocking_issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    score_percentage: float = Field(ge=0, le=100)
    reviewed_at: datetime = Field(default_factory=utc_now)

    @field_validator("reviewed_at")
    @classmethod
    def validate_reviewed_at(cls, value: datetime) -> datetime:
        return _aware(value)


class ProductionPackage(AuraBaseModel):
    """All structured, review-ready outputs for one production run."""

    package_id: UUID = Field(default_factory=uuid4)
    input: ProductionInput
    brief: ContentBrief
    script: VideoScript
    storyboard: Storyboard
    voiceover_plan: VoiceoverPlan
    visual_plan: VisualGenerationPlan
    thumbnail_plan: ThumbnailPlan
    short_form_package: ShortFormPackage
    subtitle_package: SubtitlePackage
    assembly_manifest: VideoAssemblyManifest
    quality_report: ProductionQualityReport | None = None
    current_stage: ProductionStage
    completed_stages: list[ProductionStage] = Field(default_factory=list)
    approval_status: ProductionApprovalStatus
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None

    @field_validator("created_at", "updated_at", "completed_at")
    @classmethod
    def validate_timestamps(cls, value: datetime | None) -> datetime | None:
        return _aware(value) if value is not None else None


class ProductionStageResult(AuraBaseModel):
    """Auditable result for one pipeline stage."""

    stage: ProductionStage
    employee_name: str = Field(min_length=1, max_length=150)
    employee_id: UUID | None = None
    success: bool
    output_reference: str = Field(min_length=1, max_length=1000)
    started_at: datetime
    completed_at: datetime
    warnings: list[str] = Field(default_factory=list)
    error_message: str | None = Field(default=None, max_length=5000)

    @field_validator("started_at", "completed_at")
    @classmethod
    def validate_timestamps(cls, value: datetime) -> datetime:
        return _aware(value)


class ProductionPipelineResult(AuraBaseModel):
    """Serializable final result from ProductionPipeline."""

    package: ProductionPackage
    stage_results: list[ProductionStageResult] = Field(min_length=1)
    runtime_snapshot: dict[str, Any] | None = None
    dashboard_mode: str = Field(min_length=1, max_length=100)
    sample_data: bool
    completed_at: datetime

    @field_validator("completed_at")
    @classmethod
    def validate_completed_at(cls, value: datetime) -> datetime:
        return _aware(value)


def _aware(value: datetime) -> datetime:
    """Require a timezone-aware timestamp and return it unchanged."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Production timestamps must be timezone-aware.")
    return value
