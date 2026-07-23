"""Read-only operational dashboard projection over canonical persisted state."""
from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import Field

from core import AuraBaseModel, utc_now
from mission_control.models import (
    AnalyticsInterpretation,
    AnalyticsSnapshot,
    ApprovalRequest,
    ApprovalState,
    EventRecord,
    InterpretationFinding,
    LessonEvidenceReference,
    LessonFinding,
    MissionLesson,
    MissionRecommendation,
    RecommendationEvidenceReference,
    RecommendationProposal,
    RecommendationStatus,
    MissionControlStatus,
)
from mission_control.analytics_interpretation import RULESET_VERSION
from mission_control.mission_lessons import LESSON_RULESET_VERSION
from mission_control.mission_recommendations import (
    RECOMMENDATION_RULESET_VERSION,
)
from mission_control.service import MissionControlService
from web_intelligence.evidence_providers import create_default_evidence_registry


class OperationalState(StrEnum):
    NOT_STARTED = "not started"
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"


class PipelineStageView(AuraBaseModel):
    name: str
    state: OperationalState


class MissionOperationsView(AuraBaseModel):
    mission_id: UUID
    title: str
    founder_goal: str
    status: str
    priority: str
    mission_score: float
    current_stage: str
    completed_tasks: int
    total_tasks: int
    progress_percentage: int
    pending_approval: bool
    pipeline: list[PipelineStageView]


class OperationsSummary(AuraBaseModel):
    total_missions: int
    active_missions: int
    pending_founder_approvals: int
    blocked_missions: int
    completed_missions: int
    creator_packages: int
    publishing_manifests: int
    recent_lessons: int


class FounderAttentionView(AuraBaseModel):
    title: str
    state: str
    mission_id: UUID
    detail: str


class SystemStatusView(AuraBaseModel):
    system: str
    state: str
    detail: str


class CapabilityView(AuraBaseModel):
    capability: str
    mission_id: UUID
    content_hash: str
    summary: dict[str, Any] = Field(default_factory=dict)


class DashboardMissionLesson(AuraBaseModel):
    """Typed durable mission lesson history for one interpretation."""

    latest_lesson: MissionLesson | None = None
    lesson_history: list[MissionLesson] = Field(default_factory=list)
    lesson_count: int = 0
    ruleset_version: str = LESSON_RULESET_VERSION
    confidence: str | None = None
    summary: str | None = None
    findings: list[LessonFinding] = Field(default_factory=list)
    evidence_references: list[LessonEvidenceReference] = Field(
        default_factory=list
    )
    strengths: list[LessonFinding] = Field(default_factory=list)
    weaknesses: list[LessonFinding] = Field(default_factory=list)
    unknowns: list[LessonFinding] = Field(default_factory=list)
    created_at: str | None = None
    source_analytics_interpretation_id: UUID | None = None
    source_analytics_snapshot_id: UUID | None = None
    lesson_available: bool = False
    lesson_actionable: bool = False
    lesson_blocking_reason: str | None = None
    recommendation: "DashboardMissionRecommendation" = Field(
        default_factory=lambda: DashboardMissionRecommendation()
    )


class DashboardMissionRecommendation(AuraBaseModel):
    latest_recommendation: MissionRecommendation | None = None
    recommendation_history: list[MissionRecommendation] = Field(
        default_factory=list
    )
    recommendation_count: int = 0
    ruleset_version: str = RECOMMENDATION_RULESET_VERSION
    confidence: str | None = None
    summary: str | None = None
    proposals: list[RecommendationProposal] = Field(default_factory=list)
    rationale: str | None = None
    evidence_references: list[RecommendationEvidenceReference] = Field(
        default_factory=list
    )
    status: str | None = None
    created_at: str | None = None
    decided_at: str | None = None
    decided_by: str | None = None
    founder_note: str | None = None
    source_mission_lesson_id: UUID | None = None
    source_analytics_interpretation_id: UUID | None = None
    recommendation_available: bool = False
    creation_actionable: bool = False
    review_actionable: bool = False
    blocking_reason: str | None = None


class DashboardAnalyticsInterpretation(AuraBaseModel):
    """Typed durable interpretation history for one publication."""

    latest_interpretation: AnalyticsInterpretation | None = None
    interpretation_history: list[AnalyticsInterpretation] = Field(
        default_factory=list
    )
    interpretation_count: int = 0
    ruleset_version: str = RULESET_VERSION
    overall_classification: str | None = None
    confidence: str | None = None
    strengths: list[InterpretationFinding] = Field(default_factory=list)
    weaknesses: list[InterpretationFinding] = Field(default_factory=list)
    missing_evidence: list[InterpretationFinding] = Field(default_factory=list)
    interpreted_at: str | None = None
    source_analytics_snapshot_id: UUID | None = None
    interpretation_available: bool = False
    interpretation_actionable: bool = False
    interpretation_blocking_reason: str | None = None
    lesson: DashboardMissionLesson = Field(
        default_factory=DashboardMissionLesson
    )


class DashboardPublicationAnalytics(AuraBaseModel):
    latest_snapshot: AnalyticsSnapshot | None = None
    historical_snapshots: list[AnalyticsSnapshot] = Field(default_factory=list)
    snapshot_count: int = 0
    latest_observed_at: str | None = None
    latest_imported_at: str | None = None
    has_analytics: bool = False
    analytics_actionable: bool = False
    analytics_blocking_reason: str | None = None
    interpretation: DashboardAnalyticsInterpretation = Field(
        default_factory=DashboardAnalyticsInterpretation
    )


class DashboardPublishingQueueItem(AuraBaseModel):
    mission_id: UUID
    queue_item_id: UUID
    approval_id: UUID | None
    destination: str
    manifest_hash: str
    queue_status: str
    approval_state: str | None
    founder_note: str | None
    publication_id: UUID | None = None
    external_url: str | None = None
    external_post_id: str | None = None
    confirmed_at: str | None = None
    published_by_actor: str | None = None
    is_active_generation: bool
    is_actionable: bool
    blocking_reason: str | None
    is_publication_actionable: bool = False
    publication_blocking_reason: str | None = None
    analytics: DashboardPublicationAnalytics | None = None


class DashboardOperationsProjection(AuraBaseModel):
    summary: OperationsSummary
    missions: list[MissionOperationsView]
    activity: list[EventRecord]
    attention: list[FounderAttentionView]
    systems: list[SystemStatusView]
    capabilities: list[CapabilityView]
    publishing_queue: list[DashboardPublishingQueueItem] = Field(default_factory=list)


def build_operations_projection(control: MissionControlService) -> DashboardOperationsProjection:
    """Derive the complete operations view without storing parallel state."""

    from mission_control.models import PublishingQueueStatus

    missions = control.list_missions()
    artifacts = control.list_artifacts()
    approvals = control.list_approvals()
    artifact_types = [item.artifact_type.casefold() for item in artifacts]
    active_states = {
        MissionControlStatus.CREATED, MissionControlStatus.READY,
        MissionControlStatus.RUNNING, MissionControlStatus.APPROVAL_REQUIRED,
        MissionControlStatus.PAUSED,
    }
    operations = [
        _mission_view(control, mission.mission_id)
        for mission in sorted(missions, key=lambda item: item.updated_at, reverse=True)
    ]
    summary = OperationsSummary(
        total_missions=len(missions),
        active_missions=sum(item.status in active_states for item in missions),
        pending_founder_approvals=sum(item.state == ApprovalState.PENDING for item in approvals),
        blocked_missions=sum(item.status == MissionControlStatus.BLOCKED for item in missions),
        completed_missions=sum(item.status == MissionControlStatus.COMPLETED for item in missions),
        creator_packages=sum("creator_package" in item for item in artifact_types),
        publishing_manifests=sum("publishing_manifest" in item for item in artifact_types),
        recent_lessons=sum("mission_learning.lesson" in item for item in artifact_types),
    )

    queue_items = control.list_publishing_queue_items()
    publishing_queue: list[DashboardPublishingQueueItem] = []

    for queue_item in queue_items:
        mission = next((m for m in missions if m.mission_id == queue_item.mission_id), None)
        mission_gen = mission.publishing_generation if mission else -1

        # Deterministic Projection Resolution
        matching_approvals = [
            a for a in approvals
            if a.subject_type == "publishing_queue_item"
            and a.subject_id == queue_item.queue_item_id
            and a.content_hash == queue_item.manifest_hash
            and a.state != ApprovalState.SUPERSEDED
        ]

        is_actionable = False
        blocking_reason = None

        if not queue_item.is_active:
            blocking_reason = "Queue item is not active."
        elif queue_item.generation != mission_gen:
            blocking_reason = "Historical generation."
        elif queue_item.status != PublishingQueueStatus.AWAITING_PUBLISH_APPROVAL:
            blocking_reason = f"Queue status is {queue_item.status.value}."
        elif len(matching_approvals) == 0:
            blocking_reason = "No matching approval found."
        elif len(matching_approvals) > 1:
            blocking_reason = "Ambiguous approvals exist."
        else:
            approval = matching_approvals[0]
            if approval.state != ApprovalState.PENDING:
                blocking_reason = f"Approval is {approval.state.value}."
            else:
                is_actionable = True
        
        primary_approval = matching_approvals[0] if matching_approvals else None
        
        pub_record = control.repository.get_publication_record(queue_item.queue_item_id)
        is_pub_actionable = False
        pub_blocking_reason = None
        if queue_item.status == PublishingQueueStatus.PUBLISHED_CONFIRMED and pub_record is None:
            pub_blocking_reason = "Inconsistent State: Confirmed status but missing durable record."
        elif not queue_item.is_active:
            pub_blocking_reason = "Queue item is not active."
        elif queue_item.generation != mission_gen:
            pub_blocking_reason = "Historical generation."
        elif pub_record is not None:
            pub_blocking_reason = "Already confirmed."
        elif queue_item.status != PublishingQueueStatus.READY_FOR_MANUAL_PUBLISH:
            pub_blocking_reason = f"Queue status is {queue_item.status.value}."
        else:
            is_pub_actionable = True


        analytics_view = None
        if pub_record:
            snapshots = control.repository.list_analytics_snapshots(pub_record.publication_id)
            latest = snapshots[0] if snapshots else None
            interpretations = control.repository.list_analytics_interpretations(
                pub_record.publication_id
            )
            latest_interpretation = (
                interpretations[0] if interpretations else None
            )
            lessons = control.repository.list_mission_lessons(
                pub_record.publication_id
            )
            latest_lesson = lessons[0] if lessons else None
            recommendations = (
                control.repository.list_mission_recommendations(
                    pub_record.publication_id
                )
            )
            latest_recommendation = (
                recommendations[0] if recommendations else None
            )
            current_recommendation_exists = bool(
                latest_lesson
                and control.repository.find_lesson_ruleset_recommendation(
                    latest_lesson.mission_lesson_id,
                    RECOMMENDATION_RULESET_VERSION,
                )
            )
            current_lesson_exists = bool(
                latest_interpretation
                and control.repository.find_interpretation_ruleset_lesson(
                    latest_interpretation.analytics_interpretation_id,
                    LESSON_RULESET_VERSION,
                )
            )
            current_exists = bool(
                latest
                and control.repository.find_snapshot_ruleset_interpretation(
                    latest.analytics_snapshot_id,
                    RULESET_VERSION,
                )
            )

            a_blocking = None
            a_actionable = False
            if queue_item.status != PublishingQueueStatus.PUBLISHED_CONFIRMED:
                a_blocking = "Publication not confirmed."
            else:
                a_actionable = True

            analytics_view = DashboardPublicationAnalytics(
                latest_snapshot=latest,
                historical_snapshots=snapshots[1:] if len(snapshots) > 1 else [],
                snapshot_count=len(snapshots),
                latest_observed_at=latest.observed_at.isoformat() if latest else None,
                latest_imported_at=latest.imported_at.isoformat() if latest else None,
                has_analytics=bool(snapshots),
                analytics_actionable=a_actionable,
                analytics_blocking_reason=a_blocking,
                interpretation=DashboardAnalyticsInterpretation(
                    latest_interpretation=latest_interpretation,
                    interpretation_history=interpretations[1:],
                    interpretation_count=len(interpretations),
                    overall_classification=(
                        latest_interpretation.overall_classification.value
                        if latest_interpretation
                        else None
                    ),
                    confidence=(
                        latest_interpretation.confidence.value
                        if latest_interpretation
                        else None
                    ),
                    strengths=(
                        list(latest_interpretation.strengths)
                        if latest_interpretation
                        else []
                    ),
                    weaknesses=(
                        list(latest_interpretation.weaknesses)
                        if latest_interpretation
                        else []
                    ),
                    missing_evidence=(
                        list(latest_interpretation.missing_evidence)
                        if latest_interpretation
                        else []
                    ),
                    interpreted_at=(
                        latest_interpretation.interpreted_at.isoformat()
                        if latest_interpretation
                        else None
                    ),
                    source_analytics_snapshot_id=(
                        latest_interpretation.analytics_snapshot_id
                        if latest_interpretation
                        else latest.analytics_snapshot_id if latest else None
                    ),
                    interpretation_available=bool(interpretations),
                    interpretation_actionable=bool(latest and not current_exists),
                    interpretation_blocking_reason=(
                        None
                        if latest and not current_exists
                        else (
                            "Current ruleset interpretation already exists."
                            if latest
                            else "No analytics snapshot is available."
                        )
                    ),
                    lesson=DashboardMissionLesson(
                        latest_lesson=latest_lesson,
                        lesson_history=lessons[1:],
                        lesson_count=len(lessons),
                        confidence=(
                            latest_lesson.confidence.value
                            if latest_lesson
                            else None
                        ),
                        summary=(
                            latest_lesson.summary if latest_lesson else None
                        ),
                        findings=(
                            list(latest_lesson.findings)
                            if latest_lesson
                            else []
                        ),
                        evidence_references=(
                            list(latest_lesson.evidence_references)
                            if latest_lesson
                            else []
                        ),
                        strengths=(
                            list(latest_lesson.strengths)
                            if latest_lesson
                            else []
                        ),
                        weaknesses=(
                            list(latest_lesson.weaknesses)
                            if latest_lesson
                            else []
                        ),
                        unknowns=(
                            list(latest_lesson.unknowns)
                            if latest_lesson
                            else []
                        ),
                        created_at=(
                            latest_lesson.created_at.isoformat()
                            if latest_lesson
                            else None
                        ),
                        source_analytics_interpretation_id=(
                            latest_interpretation.analytics_interpretation_id
                            if latest_interpretation
                            else None
                        ),
                        source_analytics_snapshot_id=(
                            latest_interpretation.analytics_snapshot_id
                            if latest_interpretation
                            else None
                        ),
                        lesson_available=bool(lessons),
                        lesson_actionable=bool(
                            latest_interpretation
                            and not current_lesson_exists
                        ),
                        lesson_blocking_reason=(
                            None
                            if latest_interpretation
                            and not current_lesson_exists
                            else (
                                "Current ruleset lesson already exists."
                                if latest_interpretation
                                else "No analytics interpretation is available."
                            )
                        ),
                        recommendation=DashboardMissionRecommendation(
                            latest_recommendation=latest_recommendation,
                            recommendation_history=recommendations[1:],
                            recommendation_count=len(recommendations),
                            confidence=(
                                latest_recommendation.confidence.value
                                if latest_recommendation
                                else None
                            ),
                            summary=(
                                latest_recommendation.summary
                                if latest_recommendation
                                else None
                            ),
                            proposals=(
                                list(latest_recommendation.proposals)
                                if latest_recommendation
                                else []
                            ),
                            rationale=(
                                latest_recommendation.rationale
                                if latest_recommendation
                                else None
                            ),
                            evidence_references=(
                                list(
                                    latest_recommendation.evidence_references
                                )
                                if latest_recommendation
                                else []
                            ),
                            status=(
                                latest_recommendation.status.value
                                if latest_recommendation
                                else None
                            ),
                            created_at=(
                                latest_recommendation.created_at.isoformat()
                                if latest_recommendation
                                else None
                            ),
                            decided_at=(
                                latest_recommendation.decided_at.isoformat()
                                if latest_recommendation
                                and latest_recommendation.decided_at
                                else None
                            ),
                            decided_by=(
                                latest_recommendation.decided_by
                                if latest_recommendation
                                else None
                            ),
                            founder_note=(
                                latest_recommendation.founder_note
                                if latest_recommendation
                                else None
                            ),
                            source_mission_lesson_id=(
                                latest_lesson.mission_lesson_id
                                if latest_lesson
                                else None
                            ),
                            source_analytics_interpretation_id=(
                                latest_lesson.analytics_interpretation_id
                                if latest_lesson
                                else None
                            ),
                            recommendation_available=bool(recommendations),
                            creation_actionable=bool(
                                latest_lesson
                                and not current_recommendation_exists
                            ),
                            review_actionable=bool(
                                latest_recommendation
                                and latest_recommendation.status
                                == RecommendationStatus.PENDING
                            ),
                            blocking_reason=(
                                None
                                if latest_lesson
                                and not current_recommendation_exists
                                else (
                                    "Current ruleset recommendation already "
                                    "exists."
                                    if latest_lesson
                                    else "No mission lesson is available."
                                )
                            ),
                        ),
                    ),
                ),
            )

        publishing_queue.append(DashboardPublishingQueueItem(
            mission_id=queue_item.mission_id,
            queue_item_id=queue_item.queue_item_id,
            approval_id=primary_approval.approval_id if primary_approval else queue_item.approval_id,
            destination=queue_item.destination,
            manifest_hash=queue_item.manifest_hash,
            queue_status=queue_item.status.value,
            approval_state=primary_approval.state.value if primary_approval else None,
            founder_note=queue_item.founder_note,
            publication_id=pub_record.publication_id if pub_record else None,
            external_url=pub_record.external_url if pub_record else None,
            external_post_id=pub_record.external_post_id if pub_record else None,
            confirmed_at=pub_record.confirmed_at.isoformat() if pub_record else None,
            published_by_actor=pub_record.published_by_actor if pub_record else None,
            is_active_generation=(queue_item.generation == mission_gen),
            is_actionable=is_actionable,
            blocking_reason=blocking_reason,
            is_publication_actionable=is_pub_actionable,
            publication_blocking_reason=pub_blocking_reason,
            analytics=analytics_view,
        ))

    return DashboardOperationsProjection(
        summary=summary,
        missions=operations,
        activity=control.list_events()[-30:][::-1],
        attention=_attention(missions, approvals),
        systems=_systems(),
        capabilities=[
            CapabilityView(
                capability=item.artifact_type,
                mission_id=item.mission_id,
                content_hash=item.content_hash,
                summary=item.metadata,
            )
            for item in artifacts
            if any(key in item.artifact_type.casefold() for key in (
                "evidence", "content_intelligence", "creator_package",
                "publishing_manifest", "business_metrics", "mission_learning.lesson",
            ))
        ],
        publishing_queue=publishing_queue,
    )


def _mission_view(control: MissionControlService, mission_id: UUID) -> MissionOperationsView:
    mission = control.get_mission(mission_id)
    if mission is None:
        raise KeyError(mission_id)
    tasks = control.list_tasks(mission_id)
    artifacts = control.list_artifacts(mission_id)
    approvals = control.list_approvals(mission_id)
    completed = sum(task.status.value == "completed" for task in tasks)
    progress = round(completed / len(tasks) * 100) if tasks else 0
    types = {item.artifact_type.casefold() for item in artifacts}
    pending = any(item.state == ApprovalState.PENDING for item in approvals)
    blocked = mission.status == MissionControlStatus.BLOCKED
    return MissionOperationsView(
        mission_id=mission.mission_id, title=mission.title,
        founder_goal=mission.founder_goal, status=mission.status.value,
        priority=mission.priority.value, mission_score=mission.mission_score,
        current_stage=mission.current_stage, completed_tasks=completed,
        total_tasks=len(tasks), progress_percentage=progress,
        pending_approval=pending,
        pipeline=[
            PipelineStageView(name="Evidence", state=_artifact_state(types, ("evidence", "trend", "web"), blocked)),
            PipelineStageView(name="Content Intelligence", state=_artifact_state(types, ("content_intelligence", "intelligence"), blocked)),
            PipelineStageView(name="Mission Generation", state=OperationalState.COMPLETED),
            PipelineStageView(name="Production", state=_artifact_state(types, ("creator_package", "production", "script"), blocked)),
            PipelineStageView(name="Founder Review", state=(OperationalState.BLOCKED if blocked else OperationalState.PENDING if pending else OperationalState.COMPLETED if approvals else OperationalState.NOT_STARTED)),
            PipelineStageView(name="Publishing Preparation", state=_artifact_state(types, ("publishing_manifest",), blocked)),
            PipelineStageView(name="Business Intelligence", state=_artifact_state(types, ("business_metrics",), blocked)),
            PipelineStageView(name="Mission Learning", state=_artifact_state(types, ("mission_learning.lesson",), blocked)),
        ],
    )


def _artifact_state(types: set[str], markers: tuple[str, ...], blocked: bool) -> OperationalState:
    if any(any(marker in value for marker in markers) for value in types):
        return OperationalState.COMPLETED
    return OperationalState.BLOCKED if blocked else OperationalState.NOT_STARTED


def _attention(missions, approvals: list[ApprovalRequest]) -> list[FounderAttentionView]:
    titles = {item.mission_id: item.title for item in missions}
    values = []
    for item in approvals:
        if item.state in {ApprovalState.PENDING, ApprovalState.EXPIRED, ApprovalState.REVISION_REQUESTED}:
            values.append(FounderAttentionView(
                title=titles.get(item.mission_id, "Mission approval"),
                state=item.state.value, mission_id=item.mission_id,
                detail=("Publishing manifest approval" if "publishing" in item.requested_action
                        else item.requested_action),
            ))
    for mission in missions:
        if mission.status == MissionControlStatus.BLOCKED and not any(
            item.mission_id == mission.mission_id for item in values
        ):
            values.append(FounderAttentionView(
                title=mission.title, state="blocked", mission_id=mission.mission_id,
                detail=mission.current_stage,
            ))
    return values


def _systems() -> list[SystemStatusView]:
    health = {item.provider.value: item for item in create_default_evidence_registry().health()}
    crawl = health["crawl4ai"]
    return [
        SystemStatusView(system="Mission Control", state="ready", detail="Authoritative persisted state available."),
        SystemStatusView(system="Knowledge Manager", state="ready", detail="Existing immutable knowledge service."),
        SystemStatusView(system="Evidence provider", state="offline fallback", detail="Deterministic canonical evidence is default."),
        SystemStatusView(system="Crawl4AI adapter", state="ready" if crawl.healthy else "unavailable", detail=crawl.reason),
        SystemStatusView(system="Provider Router", state="offline fallback", detail="No paid provider call is enabled."),
        SystemStatusView(system="Production pipeline", state="ready", detail="Creator-package preparation only."),
        SystemStatusView(system="Publishing execution", state="disabled", detail="Plans only; uploads and publishing are disabled."),
        SystemStatusView(system="Business Intelligence", state="offline fallback", detail="Deterministic metrics adapter."),
    ]
