"""Authoritative read model for local founder mission review."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import Field

from core import AuraBaseModel
from mission_control.models import (
    ApprovalRequest,
    ArtifactRecord,
    EventRecord,
    MissionRecord,
    TaskRecord,
)
from mission_control.service import MissionControlService


class EvidenceReference(AuraBaseModel):
    """Safe evidence or citation reference extracted from persisted provenance."""

    label: str
    value: str


class FounderReviewProjection(AuraBaseModel):
    """Selected mission state composed only from Mission Control records."""

    mission: MissionRecord
    tasks: list[TaskRecord]
    artifacts: list[ArtifactRecord]
    timeline: list[EventRecord]
    approval: ApprovalRequest | None
    evidence: list[EvidenceReference] = Field(default_factory=list)
    creative_quality: dict[str, Any] = Field(default_factory=dict)
    lessons: list[dict[str, Any]] = Field(default_factory=list)
    lesson_influence: str | None = None


def build_founder_review(
    control: MissionControlService,
    mission_id: UUID,
) -> FounderReviewProjection:
    """Build a review directly from the authoritative repository."""

    mission = control.repository.get_mission(mission_id)
    if mission is None:
        raise KeyError("Mission was not found.")
    tasks = control.repository.list_tasks(mission_id)
    artifacts = control.repository.list_artifacts(mission_id)
    approvals = control.repository.list_approvals(mission_id)
    approval = max(approvals, key=lambda item: item.issued_at) if approvals else None
    evidence: dict[tuple[str, str], EvidenceReference] = {}
    quality: dict[str, Any] = {}
    lessons: list[dict[str, Any]] = []
    for artifact in artifacts:
        if "quality" in artifact.artifact_type.casefold():
            quality = artifact.metadata
        if artifact.artifact_type == "mission_learning.lesson":
            lessons.append(artifact.metadata)
        for source in (artifact.provenance, artifact.metadata):
            _collect_references(source, evidence)
    influence = (
        mission.reasoning_summary
        if "Mission lessons changed" in mission.reasoning_summary
        else None
    )
    return FounderReviewProjection(
        mission=mission,
        tasks=tasks,
        artifacts=artifacts,
        timeline=control.repository.list_events(mission_id),
        approval=approval,
        evidence=list(evidence.values()),
        creative_quality=quality,
        lessons=lessons,
        lesson_influence=influence,
    )


def _collect_references(
    value: Any,
    output: dict[tuple[str, str], EvidenceReference],
    *,
    parent: str = "",
) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            label = f"{parent}.{key}" if parent else str(key)
            if any(word in str(key).casefold() for word in ("citation", "source", "evidence")):
                if isinstance(item, (str, int, float, UUID)):
                    reference = EvidenceReference(label=label, value=str(item))
                    output[(reference.label, reference.value)] = reference
            _collect_references(item, output, parent=label)
    elif isinstance(value, list):
        for item in value:
            _collect_references(item, output, parent=parent)
