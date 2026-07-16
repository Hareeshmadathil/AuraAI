"""Typed contracts for offline provider preparation packages."""
from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, Field


class VisualType(StrEnum):
    PRESENTER = "presenter"
    B_ROLL = "b_roll"
    SCREEN_RECORDING = "screen_recording"
    MOTION_GRAPHIC = "motion_graphic"


class ApprovalBoundaries(BaseModel):
    content_approved: bool = True
    voice_generation_approved: bool = False
    avatar_generation_approved: bool = False
    editing_approved: bool = False
    private_render_approved: bool = False
    publishing_approved: bool = False


class ScriptSegment(BaseModel):
    segment_id: str
    order: int = Field(ge=1)
    section_title: str
    narration_text: str
    estimated_duration_seconds: float = Field(gt=0)
    visual_type: VisualType
    avatar_visible: bool
    evidence_required: list[str] = Field(default_factory=list)
    asset_requirement_ids: list[str] = Field(default_factory=list)
    subtitle_references: list[str] = Field(default_factory=list)
    transition_notes: str
    founder_notes: str
    content_hash: str
    shorts_candidate: bool = False
    is_cta: bool = False


class MissionPackage(BaseModel):
    root: Path
    mission_id: UUID
    mission_title: str
    script_artifact_id: UUID
    parent_script_artifact_id: UUID
    script_version: int
    script_content_hash: str
    title: str
    sections: list[str]
    call_to_action: str
    estimated_duration_seconds: float
    quality_score: float
    quality_gate: str
    blocker_count: int
    approvals: ApprovalBoundaries = Field(default_factory=ApprovalBoundaries)


class ConnectorStatus(BaseModel):
    mission_id: UUID
    script_version: int
    quality_gate: str
    elevenlabs_ready: bool
    heygen_ready: bool
    editor_ready: bool
    youtube_ready: bool
    founder_assets_complete: int
    missing_asset_count: int
    avatar_candidate: str = "Terry (founder-selected candidate; not approved)"
    selected_voice_status: str = "Not selected / not approved"
    publishing: bool = False
    founder_action_required: bool = True
