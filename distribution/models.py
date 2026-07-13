"""Typed local-only distribution and approval models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from core import AuraBaseModel, DepartmentName, TaskPriority, TaskRecord, utc_now


class PublishingState(StrEnum):
    """Explicit states for founder-controlled manual publication."""

    NOT_READY = "not_ready"
    READY_FOR_REVIEW = "ready_for_review"
    FOUNDER_APPROVED = "founder_approved"
    READY_TO_UPLOAD = "ready_to_upload"
    UPLOADED_MANUALLY = "uploaded_manually"
    METRICS_IMPORTED = "metrics_imported"


class DistributionChannel(StrEnum):
    """Local package targets; these values never trigger an upload."""

    YOUTUBE = "youtube"
    YOUTUBE_SHORTS = "youtube_shorts"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    LINKEDIN = "linkedin"
    TWITTER_X = "twitter_x"
    COMMUNITY = "community"


class PublishChecklistItem(AuraBaseModel):
    """One verifiable condition before manual upload."""

    key: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=250)
    completed: bool = False
    required: bool = True
    guidance: str = Field(min_length=1, max_length=1000)


class ChapterMarker(AuraBaseModel):
    """One proposed long-form chapter marker."""

    timestamp_seconds: float = Field(ge=0)
    title: str = Field(min_length=1, max_length=150)


class UploadInstruction(AuraBaseModel):
    """Manual instruction that cannot execute external actions."""

    sequence: int = Field(ge=1)
    channel: DistributionChannel
    instruction: str = Field(min_length=1, max_length=1000)
    founder_confirmation_required: bool = True


class MetadataPackage(AuraBaseModel):
    """Cross-platform metadata prepared for founder review."""

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    tags: list[str] = Field(default_factory=list, max_length=30)
    hashtags: list[str] = Field(default_factory=list, max_length=30)
    playlist_suggestion: str = Field(min_length=1, max_length=200)
    chapter_markers: list[ChapterMarker] = Field(default_factory=list)
    language: str = Field(default="English", min_length=1, max_length=100)
    seo_notes: list[str] = Field(default_factory=list)


class PlatformDistributionPackage(AuraBaseModel):
    """Reviewable copy and instructions for one platform."""

    channel: DistributionChannel
    title: str = Field(min_length=1, max_length=300)
    caption: str = Field(min_length=1, max_length=5000)
    content_role: str = Field(min_length=1, max_length=500)
    tags: list[str] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list)
    upload_notes: list[str] = Field(default_factory=list)
    monetization_note: str = Field(min_length=1, max_length=1000)
    earnings_guaranteed: Literal[False] = False


class ThumbnailDistributionPackage(AuraBaseModel):
    """Truthful thumbnail selection guidance without image generation."""

    concept_reference: UUID | None = None
    headline: str = Field(min_length=1, max_length=120)
    alt_text: str = Field(min_length=1, max_length=500)
    safety_notes: list[str] = Field(default_factory=list)


class ManualApprovalChecklist(AuraBaseModel):
    """Founder confirmations required before an upload can be ready."""

    items: list[PublishChecklistItem] = Field(min_length=1)
    founder_name: str | None = Field(default=None, max_length=200)
    approved_at: datetime | None = None
    approval_note: str | None = Field(default=None, max_length=1000)

    @property
    def complete(self) -> bool:
        """Return whether every required item is confirmed."""

        return all(item.completed or not item.required for item in self.items)


class ApprovalChange(AuraBaseModel):
    """Auditable publishing-state transition."""

    previous_state: PublishingState
    new_state: PublishingState
    reason: str = Field(min_length=1, max_length=1000)
    changed_at: datetime = Field(default_factory=utc_now)


class DistributionTaskAssignment(AuraBaseModel):
    """One deterministic department assignment."""

    sequence: int = Field(ge=1)
    role: str = Field(min_length=1, max_length=150)
    output_key: str = Field(min_length=1, max_length=100)
    priority: TaskPriority = TaskPriority.HIGH


class DistributionPlan(AuraBaseModel):
    """Director-owned ordered distribution plan."""

    plan_id: UUID = Field(default_factory=uuid4)
    source_package_id: UUID
    assignments: list[DistributionTaskAssignment] = Field(min_length=1)
    created_at: datetime = Field(default_factory=utc_now)

    def to_task_records(self) -> list[TaskRecord]:
        """Convert assignments to local Distribution tasks."""

        return [
            TaskRecord(
                title=f"Distribution: {item.role}",
                department=DepartmentName.DISTRIBUTION,
                priority=item.priority,
                input_data={
                    "plan_id": str(self.plan_id),
                    "source_package_id": str(self.source_package_id),
                    "output_key": item.output_key,
                },
            )
            for item in self.assignments
        ]


class DistributionPackage(AuraBaseModel):
    """Complete local package for a founder-controlled manual upload."""

    package_id: UUID = Field(default_factory=uuid4)
    source_package_id: UUID
    source_kind: str = Field(min_length=1, max_length=100)
    publish_checklist: list[PublishChecklistItem] = Field(min_length=1)
    metadata_package: MetadataPackage
    youtube_package: PlatformDistributionPackage
    shorts_package: PlatformDistributionPackage
    instagram_package: PlatformDistributionPackage
    tiktok_package: PlatformDistributionPackage
    linkedin_package: PlatformDistributionPackage
    twitter_x_package: PlatformDistributionPackage
    community_post: PlatformDistributionPackage
    thumbnail_package: ThumbnailDistributionPackage
    hashtags: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    playlist_suggestion: str = Field(min_length=1, max_length=200)
    chapter_markers: list[ChapterMarker] = Field(default_factory=list)
    upload_instructions: list[UploadInstruction] = Field(min_length=1)
    manual_approval_checklist: ManualApprovalChecklist
    publication_status: PublishingState = PublishingState.NOT_READY
    approval_history: list[ApprovalChange] = Field(default_factory=list)
    predicted_quality_score: float | None = Field(default=None, ge=0, le=100)
    predicted_hook_score: float | None = Field(default=None, ge=0, le=100)
    predicted_retention_score: float | None = Field(default=None, ge=0, le=100)
    predicted_thumbnail_score: float | None = Field(default=None, ge=0, le=100)
    automatic_publishing: Literal[False] = False
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_channels(self) -> "DistributionPackage":
        """Ensure named package fields cannot leak another platform."""

        expected = {
            "youtube_package": DistributionChannel.YOUTUBE,
            "shorts_package": DistributionChannel.YOUTUBE_SHORTS,
            "instagram_package": DistributionChannel.INSTAGRAM,
            "tiktok_package": DistributionChannel.TIKTOK,
            "linkedin_package": DistributionChannel.LINKEDIN,
            "twitter_x_package": DistributionChannel.TWITTER_X,
            "community_post": DistributionChannel.COMMUNITY,
        }
        for field_name, channel in expected.items():
            if getattr(self, field_name).channel != channel:
                raise ValueError(f"{field_name} must target {channel.value}.")
        return self
