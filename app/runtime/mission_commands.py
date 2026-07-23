"""Normal application mission commands over the shared runtime manager."""

from __future__ import annotations

from uuid import UUID
from datetime import datetime

from pydantic import Field

from core import AuraBaseModel
from mission_control.models import (
    ApprovalRequest,
    ApprovalState,
    MalformedCommandError,
    MissionLesson,
    MissionRecommendation,
    RecommendationDecision,
    MissionRecord,
    PublishingQueueItem,
    TaskRecord,
    AnalyticsInterpretation,
    AnalyticsMetrics,
    AnalyticsSnapshot,
)
from runtime_engine.runtime_manager import MissionRuntimeManager
from runtime_engine.recovery import RecoveryReport


class RunNextTaskResult(AuraBaseModel):
    """Result returned by the normal run-next command."""

    mission_id: UUID
    executed: bool
    task: TaskRecord | None = None
    detail: str = Field(min_length=1, max_length=500)


class MissionCommandService:
    """Thin command adapter with no repository or employee access."""

    def __init__(self, runtime_manager: MissionRuntimeManager) -> None:
        self._runtime_manager = runtime_manager

    @property
    def runtime_manager(self) -> MissionRuntimeManager:
        """Return the shared authoritative runtime manager."""

        return self._runtime_manager

    def submit(self, mission: MissionRecord) -> MissionRecord:
        """Submit one new canonical mission."""

        return self._runtime_manager.create_mission(mission)

    def run_next(self, mission_id: UUID) -> RunNextTaskResult:
        """Execute only the next task selected by Mission Control."""

        task = self._runtime_manager.run_next(mission_id)
        return RunNextTaskResult(
            mission_id=mission_id,
            executed=task is not None,
            task=task,
            detail=(
                "Next eligible task executed."
                if task is not None
                else "No eligible task is ready."
            ),
        )

    def recover(self, mission_id: UUID) -> RecoveryReport:
        """Explicitly rerun global reconciliation and return this report."""

        if self._runtime_manager.mission_control.get_mission(mission_id) is None:
            raise KeyError(f"Unknown mission: {mission_id}")
        return self._runtime_manager.reconcile()

    def retry(self, mission_id: UUID, task_id: UUID) -> RunNextTaskResult:
        """Explicitly retry one policy-eligible task."""

        task = self._runtime_manager.retry_task(mission_id, task_id)
        return RunNextTaskResult(
            mission_id=mission_id,
            executed=True,
            task=task,
            detail="Eligible task retry executed.",
        )

    def resume(
        self,
        mission_id: UUID,
        task_id: UUID,
        checkpoint_id: UUID | None = None,
    ) -> RunNextTaskResult:
        """Explicitly resume from a valid checkpoint or restart policy."""

        task = self._runtime_manager.resume_task(
            mission_id,
            task_id,
            checkpoint_id,
        )
        return RunNextTaskResult(
            mission_id=mission_id,
            executed=True,
            task=task,
            detail="Eligible task resume executed.",
        )

    def submit_publish_decision(
        self,
        *,
        mission_id: UUID,
        queue_item_id: UUID,
        approval_id: UUID,
        content_hash: str,
        decision: ApprovalState,
        reason: str | None,
        actor: str,
    ) -> tuple[PublishingQueueItem, ApprovalRequest]:
        """Submit a publishing decision through the boundary."""
        if not actor or not actor.strip():
            raise MalformedCommandError("An actor must be specified.")

        if decision not in {
            ApprovalState.APPROVED,
            ApprovalState.REJECTED,
            ApprovalState.REVISION_REQUESTED,
        }:
            raise MalformedCommandError(f"Unsupported decision state: {decision}")

        return self._runtime_manager.mission_control.apply_publish_decision(
            mission_id=mission_id,
            queue_item_id=queue_item_id,
            approval_id=approval_id,
            content_hash=content_hash,
            decision=decision,
            reason=reason,
            actor=actor,
        )

    def confirm_manual_publication(
        self,
        *,
        mission_id: UUID,
        queue_item_id: UUID,
        content_hash: str,
        external_url: str | None,
        external_post_id: str | None,
        confirmation_note: str | None,
        actor: str,
    ) -> tuple[PublishingQueueItem, 'PublicationRecord']:
        """Submit a manual publication confirmation."""
        if not actor or not actor.strip():
            raise MalformedCommandError("An actor must be specified.")

        url = external_url.strip() if external_url else None
        post_id = external_post_id.strip() if external_post_id else None
        
        if not url and not post_id:
            raise MalformedCommandError("Must provide at least one of external_url or external_post_id.")
            
        if url:
            if not (url.startswith("http://") or url.startswith("https://")):
                raise MalformedCommandError("Invalid URL scheme.")

        return self._runtime_manager.mission_control.confirm_manual_publication(
            mission_id=mission_id,
            queue_item_id=queue_item_id,
            content_hash=content_hash,
            external_url=external_url,
            external_post_id=external_post_id,
            confirmation_note=confirmation_note,
            actor=actor,
        )

    def import_analytics_snapshot(
        self,
        *,
        mission_id: UUID,
        publication_id: UUID,
        observed_at: datetime,
        metrics: AnalyticsMetrics,
        actor: str,
    ) -> AnalyticsSnapshot:
        if not actor or not actor.strip():
            raise MalformedCommandError("An actor must be specified.")

        return self._runtime_manager.mission_control.import_analytics_snapshot(
            mission_id=mission_id,
            publication_id=publication_id,
            observed_at=observed_at,
            imported_by_actor=actor,
            metrics=metrics,
        )

    def interpret_analytics_snapshot(
        self,
        *,
        mission_id: UUID,
        analytics_snapshot_id: UUID,
        actor: str,
    ) -> AnalyticsInterpretation:
        """Request authoritative deterministic interpretation."""

        if not actor or not actor.strip():
            raise MalformedCommandError("An actor must be specified.")
        return self._runtime_manager.mission_control.interpret_analytics_snapshot(
            mission_id=mission_id,
            analytics_snapshot_id=analytics_snapshot_id,
            interpreted_by_actor=actor,
        )

    def create_mission_lesson(
        self,
        *,
        mission_id: UUID,
        analytics_interpretation_id: UUID,
        actor: str,
    ) -> MissionLesson:
        """Request authoritative mission lesson creation."""

        if not actor or not actor.strip():
            raise MalformedCommandError("An actor must be specified.")
        return self._runtime_manager.mission_control.create_mission_lesson(
            mission_id=mission_id,
            analytics_interpretation_id=analytics_interpretation_id,
            created_by_actor=actor,
        )

    def create_mission_recommendation(
        self,
        *,
        mission_id: UUID,
        mission_lesson_id: UUID,
        actor: str,
    ) -> MissionRecommendation:
        if not actor or not actor.strip():
            raise MalformedCommandError("An actor must be specified.")
        return (
            self._runtime_manager.mission_control
            .create_mission_recommendation(
                mission_id=mission_id,
                mission_lesson_id=mission_lesson_id,
                created_by_actor=actor,
            )
        )

    def review_mission_recommendation(
        self,
        *,
        mission_id: UUID,
        mission_recommendation_id: UUID,
        decision: RecommendationDecision,
        actor: str,
        founder_note: str | None = None,
    ) -> MissionRecommendation:
        if not actor or not actor.strip():
            raise MalformedCommandError("An actor must be specified.")
        return self._runtime_manager.mission_control.review_mission_recommendation(
            mission_id=mission_id,
            mission_recommendation_id=mission_recommendation_id,
            decision=decision,
            decided_by_actor=actor,
            founder_note=founder_note,
        )

    def create_mission_from_recommendation(
        self,
        *,
        source_mission_id: UUID,
        mission_recommendation_id: UUID,
        actor: str,
    ) -> MissionRecord:
        """Explicitly create one ordinary successor through Mission Control."""

        if not actor or not actor.strip():
            raise MalformedCommandError("An actor must be specified.")
        return (
            self._runtime_manager.mission_control
            .create_mission_from_recommendation(
                source_mission_id=source_mission_id,
                mission_recommendation_id=mission_recommendation_id,
                created_by_actor=actor,
            )
        )
