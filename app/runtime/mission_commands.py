"""Normal application mission commands over the shared runtime manager."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from core import AuraBaseModel
from mission_control.models import (
    ApprovalRequest,
    ApprovalState,
    MalformedCommandError,
    MissionRecord,
    PublishingQueueItem,
    TaskRecord,
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
