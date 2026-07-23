"""Mission lifecycle, approval, scheduling, recovery, and department bus."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import timedelta
from uuid import UUID

from core import utc_now
from mission_control.analytics_interpretation import (
    RULESET_VERSION,
    SUPPORTED_RULESETS,
    build_interpretation_payload,
    interpretation_payload_hash,
)
from mission_control.mission_lessons import (
    LESSON_RULESET_VERSION,
    SUPPORTED_LESSON_RULESETS,
    build_mission_lesson_payload,
    mission_lesson_payload_hash,
)
from mission_control.mission_recommendations import (
    RECOMMENDATION_RULESET_VERSION,
    SUPPORTED_RECOMMENDATION_RULESETS,
    build_mission_recommendation_payload,
    mission_recommendation_payload_hash,
)
from mission_control.models import (
    AnalyticsInterpretation,
    AnalyticsMetrics,
    AnalyticsSnapshot,
    ApprovalRequest, ApprovalState, ArtifactApprovalState, ArtifactRecord,
    AttemptStatus, CheckpointKind, CheckpointResumability, DepartmentCommand,
    DepartmentResult, DuplicateRecordError, ExecutionAttempt,
    FailureClassification, ItemNotFoundError, MalformedCommandError,
    MismatchError,
    RepositoryConsistencyError, RepositoryIntegrityError, StaleContentError,
    ConflictingDecisionError, MissionLesson, MissionRecommendation,
    RecommendationDecision, RecommendationStatus, TaskCheckpoint,
    EventRecord, MissionControlProjection, MissionControlStatus, MissionRecord,
    PublishingQueueStatus, RiskLevel, TaskRecord, TaskStatus, RenderJob,
    PublishingQueueItem, require_utc_datetime,
)
from mission_control.repository import MissionControlRepository


TRANSITIONS = {
    MissionControlStatus.CREATED: {MissionControlStatus.READY, MissionControlStatus.CANCELLED},
    MissionControlStatus.READY: {MissionControlStatus.RUNNING, MissionControlStatus.PAUSED, MissionControlStatus.CANCELLED},
    MissionControlStatus.RUNNING: {MissionControlStatus.APPROVAL_REQUIRED, MissionControlStatus.BLOCKED, MissionControlStatus.PAUSED, MissionControlStatus.COMPLETED, MissionControlStatus.FAILED, MissionControlStatus.CANCELLED, MissionControlStatus.FOUNDER_REVIEW_APPROVED},
    MissionControlStatus.APPROVAL_REQUIRED: {MissionControlStatus.RUNNING, MissionControlStatus.BLOCKED, MissionControlStatus.CANCELLED},
    MissionControlStatus.FOUNDER_REVIEW_APPROVED: {MissionControlStatus.RENDERING, MissionControlStatus.CANCELLED},
    MissionControlStatus.RENDERING: {MissionControlStatus.PUBLISHING_PREPARATION, MissionControlStatus.BLOCKED, MissionControlStatus.FAILED, MissionControlStatus.CANCELLED},
    MissionControlStatus.PUBLISHING_PREPARATION: {MissionControlStatus.AWAITING_PUBLISH_APPROVAL, MissionControlStatus.BLOCKED, MissionControlStatus.FAILED, MissionControlStatus.CANCELLED},
    MissionControlStatus.AWAITING_PUBLISH_APPROVAL: {MissionControlStatus.READY_FOR_MANUAL_PUBLISH, MissionControlStatus.BLOCKED, MissionControlStatus.CANCELLED},
    MissionControlStatus.READY_FOR_MANUAL_PUBLISH: {MissionControlStatus.AWAITING_MANUAL_PUBLISH_CONFIRMATION, MissionControlStatus.CANCELLED},
    MissionControlStatus.AWAITING_MANUAL_PUBLISH_CONFIRMATION: {MissionControlStatus.PUBLISHED_CONFIRMED, MissionControlStatus.CANCELLED},
    MissionControlStatus.PUBLISHED_CONFIRMED: {MissionControlStatus.COMPLETED},
    MissionControlStatus.BLOCKED: {MissionControlStatus.READY, MissionControlStatus.PAUSED, MissionControlStatus.FAILED, MissionControlStatus.CANCELLED},
    MissionControlStatus.PAUSED: {MissionControlStatus.READY, MissionControlStatus.CANCELLED},
    MissionControlStatus.COMPLETED: set(),
    MissionControlStatus.FAILED: set(),
    MissionControlStatus.CANCELLED: set(),
}


class MissionControlService:
    """Single authoritative coordination boundary."""

    def __init__(self, repository: MissionControlRepository) -> None:
        self.repository = repository

    def get_mission(self, mission_id: UUID) -> MissionRecord | None:
        """Return one authoritative mission without mutating state."""

        return self.repository.get_mission(mission_id)

    def get_task(self, task_id: UUID) -> TaskRecord | None:
        return self.repository.get_task(task_id)

    def list_missions(self) -> list[MissionRecord]:
        """Return authoritative missions for read-only consumers."""

        return self.repository.list_missions()

    def list_tasks(self, mission_id: UUID | None = None) -> list[TaskRecord]:
        """Return canonical tasks for a mission or the whole repository."""

        return self.repository.list_tasks(mission_id)

    def list_artifacts(
        self,
        mission_id: UUID | None = None,
    ) -> list[ArtifactRecord]:
        """Return canonical artifacts for read-only consumers."""

        return self.repository.list_artifacts(mission_id)

    def list_approvals(
        self,
        mission_id: UUID | None = None,
    ) -> list[ApprovalRequest]:
        """Return canonical approvals for read-only consumers."""

        return self.repository.list_approvals(mission_id)

    def list_events(self, mission_id: UUID | None = None) -> list[EventRecord]:
        """Return the canonical ordered event stream without mutation."""

        return self.repository.list_events(mission_id)

    def get_attempt(self, attempt_id: UUID) -> ExecutionAttempt | None:
        return self.repository.get_attempt(attempt_id)

    def list_attempts(
        self, mission_id: UUID | None = None
    ) -> list[ExecutionAttempt]:
        return self.repository.list_attempts(mission_id)

    def get_checkpoint(self, checkpoint_id: UUID) -> TaskCheckpoint | None:
        return self.repository.get_checkpoint(checkpoint_id)

    def list_checkpoints(
        self, mission_id: UUID | None = None
    ) -> list[TaskCheckpoint]:
        return self.repository.list_checkpoints(mission_id)

    def get_render_job(self, job_id: UUID) -> RenderJob | None:
        return self.repository.get_render_job(job_id)

    def list_render_jobs(self, mission_id: UUID | None = None) -> list[RenderJob]:
        return self.repository.list_render_jobs(mission_id)

    def save_render_job(self, job: RenderJob) -> None:
        self.repository.save_render_job(job)

    def update_render_job(self, job: RenderJob) -> None:
        self.repository.update_render_job(job)

    def get_publishing_queue_item(self, queue_item_id: UUID) -> PublishingQueueItem | None:
        return self.repository.get_publishing_queue_item(queue_item_id)

    def list_publishing_queue_items(self, mission_id: UUID | None = None) -> list[PublishingQueueItem]:
        return self.repository.list_publishing_queue_items(mission_id)

    def save_publishing_queue_item(self, item: PublishingQueueItem) -> None:
        self.repository.save_publishing_queue_item(item)

    def update_publishing_queue_item(self, item: PublishingQueueItem) -> None:
        self.repository.update_publishing_queue_item(item)

    def begin_attempt(
        self,
        task_id: UUID,
        employee_id: UUID,
        *,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> ExecutionAttempt:
        """Persist an execution attempt before dispatch begins."""

        task = self._task(task_id)
        active = [
            item for item in self.repository.list_attempts(task.mission_id)
            if item.task_id == task_id and item.status == AttemptStatus.STARTED
        ]
        if active:
            raise ValueError("Task already has an active execution attempt.")
        attempt = ExecutionAttempt(
            mission_id=task.mission_id,
            task_id=task_id,
            employee_id=employee_id,
            attempt_number=task.attempts + 1,
            starting_task_state=task.status,
            correlation_id=correlation_id,
            causation_id=causation_id,
        )
        self.repository.save_attempt(attempt)
        self._event("attempt.started", task.mission_id, task_id, {
            "attempt_id": str(attempt.attempt_id),
            "correlation_id": str(correlation_id),
        })
        return attempt

    def finish_attempt(
        self,
        attempt_id: UUID,
        result: DepartmentResult,
    ) -> ExecutionAttempt:
        """Persist one immutable terminal outcome for an active attempt."""

        attempt = self.repository.get_attempt(attempt_id)
        if attempt is None:
            raise KeyError(f"Unknown attempt: {attempt_id}")
        if attempt.status != AttemptStatus.STARTED:
            return attempt
        if (result.mission_id, result.task_id) != (
            attempt.mission_id, attempt.task_id
        ):
            raise ValueError("Attempt result correlation does not match.")
        task = self._task(attempt.task_id)
        retry_eligible = (
            not result.success
            and result.retryable
            and task.attempts < task.maximum_attempts
        )
        classification = (
            FailureClassification.NONE
            if result.success
            else FailureClassification.RETRYABLE
            if retry_eligible
            else FailureClassification.EXHAUSTED
            if task.attempts >= task.maximum_attempts
            else FailureClassification.NON_RETRYABLE
        )
        updated = attempt.model_copy(update={
            "status": AttemptStatus.COMPLETED if result.success else AttemptStatus.FAILED,
            "failure_classification": classification,
            "error_summary": result.error_code,
            "result_reference": str(result.command_id),
            "retry_eligible": retry_eligible,
            "finished_at": result.completed_at,
        })
        self.repository.update_attempt(updated)
        self._event("attempt.finished", attempt.mission_id, attempt.task_id, {
            "attempt_id": str(attempt_id), "status": updated.status.value,
            "failure_classification": classification.value,
        })
        return updated

    def interrupt_attempt(self, attempt_id: UUID) -> ExecutionAttempt:
        """Mark a crash-like active attempt interrupted exactly once."""

        attempt = self.repository.get_attempt(attempt_id)
        if attempt is None:
            raise KeyError(f"Unknown attempt: {attempt_id}")
        if attempt.status != AttemptStatus.STARTED:
            return attempt
        task = self._task(attempt.task_id)
        retry_eligible = (
            task.attempts < task.maximum_attempts
            and task.retry_mode.value == "explicit"
        )
        updated = attempt.model_copy(update={
            "status": AttemptStatus.INTERRUPTED,
            "failure_classification": FailureClassification.INTERRUPTED,
            "error_summary": "Process ended before result acceptance.",
            "retry_eligible": retry_eligible,
            "finished_at": utc_now(),
        })
        self.repository.update_attempt(updated)
        self._event("attempt.interrupted", attempt.mission_id, attempt.task_id, {
            "attempt_id": str(attempt_id),
        })
        return updated

    def create_checkpoint(
        self,
        *,
        attempt_id: UUID,
        kind: CheckpointKind,
        payload: dict[str, object],
        producer_employee_id: UUID,
        resumability: CheckpointResumability,
        artifact_reference: str | None = None,
        schema_version: int = 1,
        expected_hash: str | None = None,
    ) -> TaskCheckpoint:
        """Validate and persist an auditable checkpoint."""

        attempt = self.repository.get_attempt(attempt_id)
        if attempt is None:
            raise ValueError("Checkpoint attempt does not exist.")
        if attempt.employee_id != producer_employee_id:
            raise ValueError("Checkpoint producer does not own the attempt.")
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        payload_hash = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        if expected_hash is not None and expected_hash != payload_hash:
            raise ValueError("Checkpoint payload checksum does not match.")
        sequence = 1 + max(
            (item.sequence for item in self.repository.list_checkpoints(attempt.mission_id)
             if item.task_id == attempt.task_id),
            default=0,
        )
        checkpoint = TaskCheckpoint(
            mission_id=attempt.mission_id,
            task_id=attempt.task_id,
            attempt_id=attempt_id,
            sequence=sequence,
            kind=kind,
            payload=payload,
            artifact_reference=artifact_reference,
            payload_hash=payload_hash,
            producer_employee_id=producer_employee_id,
            resumability=resumability,
            schema_version=schema_version,
        )
        self.repository.save_checkpoint(checkpoint)
        self._event("checkpoint.created", attempt.mission_id, attempt.task_id, {
            "checkpoint_id": str(checkpoint.checkpoint_id),
            "attempt_id": str(attempt_id), "sequence": sequence,
        })
        return checkpoint

    def create_mission(self, mission: MissionRecord) -> MissionRecord:
        self.repository.save_mission(mission)
        self._event("mission.created", mission.mission_id)
        return mission

    def transition(self, mission_id: UUID, status: MissionControlStatus, *, stage: str | None = None) -> MissionRecord:
        mission = self._mission(mission_id)
        if status not in TRANSITIONS[mission.status]:
            raise ValueError(f"Forbidden mission transition: {mission.status} -> {status}")
        updated = mission.model_copy(update={"status": status, "current_stage": stage or mission.current_stage, "updated_at": utc_now()})
        self.repository.update_mission(updated)
        self._event("mission.transitioned", mission_id, payload={"from": mission.status.value, "to": status.value})
        return updated

    def add_task(self, task: TaskRecord) -> TaskRecord:
        self._mission(task.mission_id)
        known = {item.task_id for item in self.repository.list_tasks(task.mission_id)}
        missing = set(task.dependencies) - known
        if missing:
            raise ValueError(f"Unknown task dependencies: {sorted(map(str, missing))}")
        self.repository.save_task(task)
        self._event("task.created", task.mission_id, task.task_id)
        return task

    def register_artifact(
        self,
        *,
        mission_id: UUID,
        task_id: UUID,
        artifact_type: str,
        location: str,
        value: object,
        provenance: dict[str, object],
        approval_state: ArtifactApprovalState = ArtifactApprovalState.PENDING,
        artifact_id: UUID | None = None,
    ) -> ArtifactRecord:
        """Register a deterministic logical artifact produced by one task."""

        self._mission(mission_id)
        self._task(task_id)
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
        artifact = ArtifactRecord(
            **({"artifact_id": artifact_id} if artifact_id else {}),
            mission_id=mission_id,
            task_id=task_id,
            artifact_type=artifact_type,
            location=location,
            content_hash=hashlib.sha256(payload.encode("utf-8")).hexdigest(),
            provenance=provenance,
            metadata=value if isinstance(value, dict) else {"value": str(value)},
            approval_state=approval_state,
        )
        self.repository.save_artifact(artifact)
        self._event(
            "artifact.registered",
            mission_id,
            task_id,
            {"artifact_id": str(artifact.artifact_id), "type": artifact_type},
        )
        return artifact

    def next_actions(self, mission_id: UUID) -> list[TaskRecord]:
        tasks = self.repository.list_tasks(mission_id)
        by_id = {item.task_id: item for item in tasks}
        selected = []
        for task in tasks:
            if task.status not in {TaskStatus.PENDING, TaskStatus.RETRY_PENDING, TaskStatus.BLOCKED}:
                continue
            if task.next_eligible_at is not None and task.next_eligible_at > utc_now():
                continue
            dependencies = [by_id[item] for item in task.dependencies]
            if any(item.status in {TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.BLOCKED} for item in dependencies):
                self._update_task(task.model_copy(update={"status": TaskStatus.BLOCKED, "blocking_reason": "A dependency cannot complete.", "updated_at": utc_now()}))
                continue
            if all(item.status == TaskStatus.COMPLETED for item in dependencies):
                if task.attempts >= task.maximum_attempts:
                    self._update_task(task.model_copy(update={"status": TaskStatus.FAILED, "blocking_reason": "Retry limit reached.", "updated_at": utc_now()}))
                    continue
                if task.consequential and not self.has_valid_approval(task):
                    self._update_task(task.model_copy(update={"status": TaskStatus.APPROVAL_REQUIRED, "blocking_reason": "Valid founder approval required.", "updated_at": utc_now()}))
                    continue
                selected.append(task.model_copy(update={"status": TaskStatus.READY, "blocking_reason": None, "updated_at": utc_now()}))
        return sorted(selected, key=lambda item: (item.created_at, str(item.task_id)))

    def dispatch(
        self,
        task_id: UUID,
        *,
        command_id: UUID | None = None,
    ) -> DepartmentCommand:
        task = self._task(task_id)
        if task.status == TaskStatus.COMPLETED:
            raise ValueError("Completed task dispatch would violate idempotency.")
        ready = {item.task_id for item in self.next_actions(task.mission_id)}
        if task_id not in ready:
            raise ValueError("Task is not the authoritative next action.")
        running = task.model_copy(update={"status": TaskStatus.RUNNING, "attempts": task.attempts + 1, "updated_at": utc_now()})
        self._update_task(running)
        self._event("task.dispatched", task.mission_id, task.task_id, {"attempt": running.attempts})
        return DepartmentCommand(
            **({"command_id": command_id} if command_id is not None else {}),
            mission_id=task.mission_id,
            task_id=task.task_id,
            department=task.department,
            assigned_agent_id=task.assigned_agent_id,
            operation=task.title,
            payload=task.payload,
            idempotency_key=task.idempotency_key,
        )

    def dispatch_preview(self, task_id: UUID) -> DepartmentCommand:
        """Build the pending command for employee resolution without mutation."""

        task = self._task(task_id)
        ready = {item.task_id for item in self.next_actions(task.mission_id)}
        if task_id not in ready:
            raise ValueError("Task is not the authoritative next action.")
        return DepartmentCommand(
            mission_id=task.mission_id,
            task_id=task.task_id,
            department=task.department,
            assigned_agent_id=task.assigned_agent_id,
            operation=task.title,
            payload=task.payload,
            idempotency_key=task.idempotency_key,
        )

    def accept_result(self, result: DepartmentResult) -> TaskRecord:
        task = self._task(result.task_id)
        if result.mission_id != task.mission_id:
            raise ValueError("Result mission does not match the task.")
        if task.status == TaskStatus.COMPLETED:
            return task
        if task.status != TaskStatus.RUNNING:
            raise ValueError("Only a running task may accept a result.")
        retry_eligible = (
            not result.success
            and result.retryable
            and task.retry_mode.value == "explicit"
            and task.attempts < task.maximum_attempts
        )
        status = (
            TaskStatus.COMPLETED if result.success
            else TaskStatus.RETRY_PENDING if retry_eligible
            else TaskStatus.FAILED if task.attempts >= task.maximum_attempts
            else TaskStatus.BLOCKED
        )
        classification = (
            FailureClassification.NONE if result.success
            else FailureClassification.RETRYABLE if retry_eligible
            else FailureClassification.EXHAUSTED if task.attempts >= task.maximum_attempts
            else FailureClassification.NON_RETRYABLE
        )
        delay = round(
            task.retry_delay_seconds
            * (task.backoff_multiplier ** max(task.attempts - 1, 0))
        )
        updated = task.model_copy(update={
            "status": status,
            "blocking_reason": result.error_code,
            "last_failure_classification": classification,
            "next_eligible_at": (
                utc_now() + timedelta(seconds=delay)
                if retry_eligible else None
            ),
            "updated_at": utc_now(),
        })
        self._update_task(updated)
        self._event(
            "task.completed" if result.success else "task.failed",
            task.mission_id,
            task.task_id,
            {"title": task.title},
        )
        return updated

    def request_approval(
        self,
        task: TaskRecord,
        *,
        expires_in: timedelta = timedelta(hours=24),
        checkpoint_id: UUID | None = None,
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
    ) -> ApprovalRequest:
        if not task.required_action or not task.required_artifact_hash:
            raise ValueError("Approval requires an action and content hash.")
        approval = ApprovalRequest(
            mission_id=task.mission_id,
            task_id=task.task_id,
            requested_action=task.required_action,
            risk=RiskLevel.CONSEQUENTIAL,
            content_hash=task.required_artifact_hash,
            expires_at=utc_now()+expires_in,
            checkpoint_id=checkpoint_id,
            **({"correlation_id": correlation_id} if correlation_id else {}),
            causation_id=causation_id,
        )
        self.repository.save_approval(approval)
        self._event("approval.requested", task.mission_id, task.task_id, {
            "approval_id": str(approval.approval_id),
            "correlation_id": str(approval.correlation_id),
            "causation_id": str(causation_id) if causation_id else None,
            "checkpoint_id": str(checkpoint_id) if checkpoint_id else None,
            "content_hash": approval.content_hash,
        })
        return approval

    def decide_approval(
        self,
        approval_id: UUID,
        state: ApprovalState,
        *,
        approver: str,
        reason: str,
        mission_id: UUID | None = None,
        task_id: UUID | None = None,
        requested_action: str | None = None,
        content_hash: str | None = None,
    ) -> ApprovalRequest:
        if state not in {
            ApprovalState.APPROVED,
            ApprovalState.REJECTED,
            ApprovalState.REVISION_REQUESTED,
        }:
            raise ValueError("Unsupported founder approval decision.")
        current = self._approval(approval_id)
        bindings = (
            (mission_id, current.mission_id, "mission"),
            (task_id, current.task_id, "task"),
            (requested_action, current.requested_action, "action"),
            (content_hash, current.content_hash, "content hash"),
        )
        if any(supplied is not None and supplied != stored for supplied, stored, _ in bindings):
            raise ValueError("Approval request binding does not match persisted authority.")
        if current.state != ApprovalState.PENDING:
            raise ValueError("Only pending approval may be decided.")
        if current.expires_at <= utc_now():
            expired=current.model_copy(update={"state":ApprovalState.EXPIRED,"decided_at":utc_now()}); self.repository.save_approval(expired); raise ValueError("Approval has expired.")
        updated=current.model_copy(update={"state":state,"approver":approver,"reason":reason,"decided_at":utc_now()})
        self.repository.save_approval(updated); self._event(f"approval.{state.value}",current.mission_id,current.task_id,{"approval_id":str(current.approval_id),"correlation_id":str(current.correlation_id),"causation_id":str(current.causation_id) if current.causation_id else None,"content_hash":current.content_hash,"checkpoint_id":str(current.checkpoint_id) if current.checkpoint_id else None,"approver":approver,"reason":reason}); return updated

    def apply_founder_decision(
        self,
        approval_id: UUID,
        state: ApprovalState,
        *,
        mission_id: UUID,
        task_id: UUID,
        requested_action: str,
        content_hash: str,
        reason: str,
    ) -> ApprovalRequest:
        """Apply one exact, local founder decision without downstream execution."""

        if not reason.strip():
            raise ValueError("A founder reason is required.")
        mission = self._mission(mission_id)
        task = self._task(task_id)
        if mission.status != MissionControlStatus.APPROVAL_REQUIRED:
            raise ValueError("Mission is not waiting for founder approval.")
        if task.status != TaskStatus.APPROVAL_REQUIRED:
            raise ValueError("Task is not waiting for founder approval.")
        decision = self.decide_approval(
            approval_id,
            state,
            approver="Local Founder",
            reason=reason.strip(),
            mission_id=mission_id,
            task_id=task_id,
            requested_action=requested_action,
            content_hash=content_hash,
        )
        if state == ApprovalState.APPROVED:
            self._update_task(task.model_copy(update={
                "status": TaskStatus.COMPLETED,
                "blocking_reason": None,
                "updated_at": utc_now(),
            }))
            self.transition(mission_id, MissionControlStatus.RUNNING, stage="founder_approved")
            self.transition(mission_id, MissionControlStatus.COMPLETED, stage="review_complete")
        else:
            self.transition(
                mission_id,
                MissionControlStatus.BLOCKED,
                stage="founder_revision" if state == ApprovalState.REVISION_REQUESTED else "founder_rejected",
            )
            self._update_task(task.model_copy(update={
                "status": TaskStatus.RETRY_PENDING if state == ApprovalState.REVISION_REQUESTED else TaskStatus.BLOCKED,
                "blocking_reason": reason.strip(),
                "updated_at": utc_now(),
            }))
        self._event(
            "founder.decision",
            mission_id,
            task_id,
            {"decision": state.value, "reason": reason.strip(), "approval_id": str(approval_id)},
        )
        return decision

    def revoke_approval(self, approval_id: UUID, *, approver: str, reason: str) -> ApprovalRequest:
        current=self._approval(approval_id)
        if current.state != ApprovalState.APPROVED: raise ValueError("Only approved authorization may be revoked.")
        updated=current.model_copy(update={"state":ApprovalState.REVOKED,"approver":approver,"reason":reason,"decided_at":utc_now()})
        self.repository.save_approval(updated); return updated

    def has_valid_approval(self, task: TaskRecord) -> bool:
        now=utc_now()
        return any(item.state==ApprovalState.APPROVED and item.task_id==task.task_id and item.mission_id==task.mission_id and item.requested_action==task.required_action and item.content_hash==task.required_artifact_hash and item.expires_at>now for item in self.repository.list_approvals(task.mission_id))

    def recover_interrupted(self) -> list[TaskRecord]:
        recovered=[]
        for task in self.repository.list_tasks():
            if task.status != TaskStatus.RUNNING: continue
            status=(
                TaskStatus.APPROVAL_REQUIRED if task.consequential
                else TaskStatus.RETRY_PENDING
                if task.attempts < task.maximum_attempts
                and task.retry_mode.value == "explicit"
                else TaskStatus.FAILED
            )
            updated=task.model_copy(update={"status":status,"blocking_reason":"Interrupted process recovered; dispatch was not repeated.","updated_at":utc_now()})
            self._update_task(updated); self._event("task.interrupted",task.mission_id,task.task_id); recovered.append(updated)
        return recovered

    def record_recovery_report(self, report: object) -> EventRecord:
        """Append an auditable summary without exposing repository writes."""

        payload = report.model_dump(mode="json") if hasattr(report, "model_dump") else {}
        return self._event("recovery.reconciled", payload=payload)

    def replay(self, mission_id: UUID) -> list[EventRecord]:
        return self.repository.list_events(mission_id)

    def start_publishing_generation(
        self, mission_id: UUID, destinations: list[str], generation_key: str
    ) -> MissionRecord:
        from mission_control.models import normalize_destinations, ConflictingDecisionError
        with self.repository.transaction():
            mission = self._mission(mission_id)
            normalized = normalize_destinations(destinations)
            if mission.publishing_generation > 0:
                if mission.publishing_generation_key == generation_key:
                    if mission.required_publish_destinations == normalized:
                        return mission
                    raise ConflictingDecisionError("Conflict: Same generation_key with different destinations.")
            updated = mission.model_copy(update={
                "publishing_generation": mission.publishing_generation + 1,
                "publishing_generation_key": generation_key,
                "required_publish_destinations": normalized,
                "updated_at": utc_now()
            })
            self.repository.update_mission(updated)
            self._event("publishing.generation_started", mission_id, payload={
                "generation": updated.publishing_generation,
                "generation_key": generation_key,
                "destinations": normalized
            })
            return updated

    def apply_publish_decision(
        self,
        mission_id: UUID,
        queue_item_id: UUID,
        approval_id: UUID,
        content_hash: str,
        decision: ApprovalState,
        reason: str | None,
        actor: str,
    ) -> tuple[PublishingQueueItem, ApprovalRequest]:
        from mission_control.models import PublishingQueueStatus, ConflictingDecisionError, ItemNotFoundError, StaleContentError, MismatchError, MalformedCommandError
        import uuid

        if decision in {ApprovalState.REJECTED, ApprovalState.REVISION_REQUESTED}:
            if not reason or not reason.strip():
                raise MalformedCommandError("A reason is required for rejection or revision requests.")

        reason_val = reason.strip() if reason else ""

        with self.repository.transaction():
            queue_item = self.repository.get_publishing_queue_item(queue_item_id)
            if queue_item is None:
                raise ItemNotFoundError("Queue item not found.")

            try:
                mission = self._mission(mission_id)
            except KeyError:
                raise ItemNotFoundError("Mission not found.")

            try:
                approval = self._approval(approval_id)
            except KeyError:
                raise ItemNotFoundError("Approval not found.")

            if queue_item.mission_id != mission_id:
                raise MismatchError("Queue item mission ID mismatch.")
            if approval.mission_id != mission_id:
                raise MismatchError("Approval mission ID mismatch.")
            if approval.subject_type != "publishing_queue_item":
                raise MismatchError("Approval subject type is not publishing_queue_item.")
            if approval.subject_id != queue_item_id:
                raise MismatchError("Approval subject ID mismatch.")

            if not queue_item.is_active:
                raise ConflictingDecisionError("Queue item is not active.")
            if queue_item.generation != mission.publishing_generation:
                raise ConflictingDecisionError("Queue item generation mismatch.")

            if content_hash != queue_item.manifest_hash:
                raise StaleContentError("Submitted content hash mismatch.")
            if approval.content_hash != queue_item.manifest_hash:
                raise StaleContentError("Approval content hash mismatch.")

            if approval.state == ApprovalState.SUPERSEDED:
                raise ConflictingDecisionError("Approval is superseded.")

            if queue_item.status in {PublishingQueueStatus.READY_FOR_MANUAL_PUBLISH, PublishingQueueStatus.PUBLISHED_CONFIRMED, PublishingQueueStatus.AWAITING_MANUAL_PUBLISH_CONFIRMATION}:
                if decision == ApprovalState.APPROVED:
                    return queue_item, approval
                else:
                    raise ConflictingDecisionError("Cannot regress already approved/published item.")

            if queue_item.status == PublishingQueueStatus.REJECTED:
                if decision == ApprovalState.REJECTED:
                    return queue_item, approval
                else:
                    raise ConflictingDecisionError("Cannot alter rejected queue item. Start new generation.")

            if queue_item.status == PublishingQueueStatus.REVISION_REQUESTED:
                if decision == ApprovalState.REVISION_REQUESTED:
                    if queue_item.founder_note == reason_val:
                        return queue_item, approval
                    raise ConflictingDecisionError("Cannot alter reason for revision. Start new generation.")
                else:
                    raise ConflictingDecisionError("Cannot alter revision request. Start new generation.")

            if decision == ApprovalState.APPROVED:
                q_status = PublishingQueueStatus.READY_FOR_MANUAL_PUBLISH
            elif decision == ApprovalState.REJECTED:
                q_status = PublishingQueueStatus.REJECTED
            elif decision == ApprovalState.REVISION_REQUESTED:
                q_status = PublishingQueueStatus.REVISION_REQUESTED
            else:
                raise MalformedCommandError("Unsupported founder publish decision.")

            updated_queue = queue_item.model_copy(update={
                "status": q_status,
                "founder_note": reason_val,
                "updated_at": utc_now()
            })
            self.repository.update_publishing_queue_item(updated_queue)

            updated_approval = approval.model_copy(update={
                "state": decision,
                "approver": actor,
                "reason": reason_val,
                "decided_at": utc_now()
            })
            self.repository.save_approval(updated_approval)

            event_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"publish_decision:{approval_id}:{decision.value}:{queue_item.manifest_hash}")
            try:
                self.repository.append_event(EventRecord(
                    event_id=event_id,
                    event_type="publish_decision.applied",
                    mission_id=queue_item.mission_id,
                    payload={
                        "queue_item_id": str(queue_item_id),
                        "approval_id": str(approval_id),
                        "decision": decision.value,
                        "reason": reason_val,
                        "actor": actor
                    }
                ))
            except Exception:
                pass

            self._evaluate_mission_publishing_readiness(queue_item.mission_id)
            return updated_queue, updated_approval

    def _evaluate_mission_publishing_readiness(self, mission_id: UUID) -> None:
        from mission_control.models import PublishingQueueStatus
        mission = self._mission(mission_id)
        if mission.status != MissionControlStatus.AWAITING_PUBLISH_APPROVAL:
            return

        queue_items = self.repository.list_publishing_queue_items(mission_id)
        ready_count = 0
        for dest in mission.required_publish_destinations:
            active = [q for q in queue_items if q.destination == dest and q.is_active and q.generation == mission.publishing_generation]
            if len(active) == 1 and active[0].status == PublishingQueueStatus.READY_FOR_MANUAL_PUBLISH:
                ready_count += 1

        if ready_count == len(mission.required_publish_destinations) and ready_count > 0:
            self.transition(mission_id, MissionControlStatus.READY_FOR_MANUAL_PUBLISH, stage="publish_approved")

    def confirm_manual_publication(
        self,
        mission_id: UUID,
        queue_item_id: UUID,
        content_hash: str,
        external_url: str | None,
        external_post_id: str | None,
        confirmation_note: str | None,
        actor: str,
    ) -> tuple['PublishingQueueItem', 'PublicationRecord']:
        from mission_control.models import PublishingQueueStatus, ConflictingDecisionError, ItemNotFoundError, StaleContentError, MismatchError, MalformedCommandError, PublicationRecord, EventRecord
        import uuid
        import urllib.parse

        # A. Early Validation
        queue_item = self.repository.get_publishing_queue_item(queue_item_id)
        if queue_item is None:
            raise ItemNotFoundError("Queue item not found.")
        
        if queue_item.mission_id != mission_id:
            raise MismatchError("Queue item mission ID mismatch.")

        try:
            mission = self._mission(mission_id)
        except KeyError:
            raise ItemNotFoundError("Mission not found.")
        
        if queue_item.generation != mission.publishing_generation:
            raise ConflictingDecisionError("Queue item generation mismatch.")
            
        if not queue_item.is_active:
            raise ConflictingDecisionError("Queue item is not active.")

        approval = self.repository.get_approval(queue_item.approval_id) if queue_item.approval_id else None
        if approval is None or approval.state != "approved":
            raise ConflictingDecisionError("Founder approval is missing or not approved.")

        if content_hash != queue_item.manifest_hash:
            raise StaleContentError("Submitted content hash mismatch.")

        # B. Normalize and validate evidence
        url = external_url.strip() if external_url else None
        post_id = external_post_id.strip() if external_post_id else None
        note = confirmation_note.strip() if confirmation_note else None
        url = url if url else None
        post_id = post_id if post_id else None
        note = note if note else None

        if not url and not post_id:
            raise MalformedCommandError("Must provide at least one of external_url or external_post_id.")

        if url:
            if not (url.startswith("http://") or url.startswith("https://")):
                raise MalformedCommandError("Invalid URL scheme.")
            parsed = urllib.parse.urlparse(url)
            if not parsed.netloc:
                raise MalformedCommandError("Invalid URL hostname.")
            if len(url) > 2000:
                raise MalformedCommandError("URL too long.")

        if post_id and len(post_id) > 150:
            raise MalformedCommandError("Post ID too long.")
        if note and len(note) > 2000:
            raise MalformedCommandError("Confirmation note too long.")

        # C. Look up PublicationRecord
        existing_record = self.repository.get_publication_record(queue_item_id)

        # D. Idempotent-Retry Branch
        if existing_record:
            if (existing_record.mission_id == mission_id and
                existing_record.destination == queue_item.destination and
                existing_record.content_hash == content_hash and
                existing_record.external_url == url and
                existing_record.external_post_id == post_id and
                existing_record.confirmation_note == note):
                return queue_item, existing_record
            else:
                raise ConflictingDecisionError("Conflicting publication evidence provided for already-confirmed item.")

        # E. First-Confirmation Branch
        if queue_item.status != PublishingQueueStatus.READY_FOR_MANUAL_PUBLISH:
            if queue_item.status == PublishingQueueStatus.PUBLISHED_CONFIRMED:
                raise ConflictingDecisionError("Inconsistent state: PUBLISHED_CONFIRMED without a durable record. Blocked.")
            else:
                raise ConflictingDecisionError(f"Cannot confirm publication for status {queue_item.status.value}")

        new_record = PublicationRecord(
            mission_id=mission_id,
            queue_item_id=queue_item_id,
            destination=queue_item.destination,
            content_hash=content_hash,
            external_url=url,
            external_post_id=post_id,
            confirmation_note=note,
            published_by_actor=actor,
        )

        try:
            with self.repository.transaction():
                self.repository.save_publication_record(new_record)
                
                updated_queue = queue_item.model_copy(update={
                    "status": PublishingQueueStatus.PUBLISHED_CONFIRMED,
                    "updated_at": utc_now()
                })
                self.repository.update_publishing_queue_item(updated_queue)
                
                event_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"publication_confirmation:{new_record.publication_id}")
                self.repository.append_event(EventRecord(
                    event_id=event_id,
                    event_type="publication.confirmed",
                    mission_id=mission_id,
                    payload={
                        "publication_id": str(new_record.publication_id),
                        "mission_id": str(mission_id),
                        "queue_item_id": str(queue_item_id),
                        "destination": queue_item.destination,
                        "content_hash": content_hash,
                        "actor": actor,
                        "confirmed_at": new_record.confirmed_at.isoformat(),
                        "external_url": url,
                        "external_post_id": post_id,
                        "confirmation_note": note,
                    }
                ))
                return updated_queue, new_record
        except ValueError as err:
            if (
                "unique constraint failed" in str(err).lower()
                or "duplicate" in str(err).lower()
                or "integrity" in str(err).lower()
            ):
                winner = self.repository.get_publication_record(queue_item_id)
                if winner:
                    if (winner.mission_id == mission_id and
                        winner.destination == queue_item.destination and
                        winner.content_hash == content_hash and
                        winner.external_url == url and
                        winner.external_post_id == post_id and
                        winner.confirmation_note == note):
                        return queue_item, winner
                    raise ConflictingDecisionError("Conflicting publication evidence from concurrent race.")
            raise

    def projection(self) -> MissionControlProjection:
        tasks=self.repository.list_tasks(); approvals=self.repository.list_approvals()
        artifacts = self.repository.list_artifacts()
        outcomes = [item.metadata for item in artifacts if item.artifact_type == "mission_learning.outcome"]
        lessons = [item.metadata for item in artifacts if item.artifact_type == "mission_learning.lesson"]
        pending_lessons = [item.metadata for item in artifacts if item.artifact_type == "mission_learning.lesson" and item.approval_state == ArtifactApprovalState.PENDING]
        influences = [mission.reasoning_summary for mission in self.repository.list_missions() if "Mission lessons changed" in mission.reasoning_summary]
        return MissionControlProjection(missions=self.repository.list_missions(),pending_approvals=[a for a in approvals if a.state==ApprovalState.PENDING],blocked_tasks=[t for t in tasks if t.status in {TaskStatus.BLOCKED,TaskStatus.APPROVAL_REQUIRED}],recent_events=self.repository.list_events()[-50:],artifacts=artifacts,recent_mission_outcomes=outcomes,generated_lessons=lessons,pending_lesson_approvals=pending_lessons,lesson_influences=influences,system_health="operational",attempts=self.repository.list_attempts(),checkpoints=self.repository.list_checkpoints(),render_jobs=self.repository.list_render_jobs(),publishing_queue=self.repository.list_publishing_queue_items())

    def _event(self,event_type,mission_id=None,task_id=None,payload=None): return self.repository.append_event(EventRecord(event_type=event_type,mission_id=mission_id,task_id=task_id,payload=payload or {}))
    def _mission(self,i):
        value=self.repository.get_mission(i)
        if value is None: raise KeyError(f"Unknown mission: {i}")
        return value
    def _task(self,i):
        value=self.repository.get_task(i)
        if value is None: raise KeyError(f"Unknown task: {i}")
        return value
    def _approval(self,i):
        value=self.repository.get_approval(i)
        if value is None: raise KeyError(f"Unknown approval: {i}")
        return value
    def _update_task(self,value): self.repository.update_task(value)


    def _generate_payload_hash(self, metrics: AnalyticsMetrics) -> str:
        dump = metrics.model_dump(mode="json", exclude_none=True)
        if "revenue_amount" in dump and dump["revenue_amount"] is not None:
            from decimal import Decimal
            normalized = Decimal(str(dump["revenue_amount"])).normalize()
            s = format(normalized, 'f')
            if '.' in s:
                s = s.rstrip('0').rstrip('.')
            dump["revenue_amount"] = s

        encoded = json.dumps(dump, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def import_analytics_snapshot(
        self,
        *,
        mission_id: UUID,
        publication_id: UUID,
        observed_at: datetime,
        imported_by_actor: str,
        metrics: AnalyticsMetrics,
    ) -> AnalyticsSnapshot:
        now = utc_now()
        observed_at = require_utc_datetime(
            observed_at,
            field_name="observed_at",
        )
        if observed_at > now + timedelta(minutes=5):
            raise StaleContentError(f"Observation timestamp {observed_at} is too far in the future.")

        pub_record = self.repository.get_publication_record_by_id(publication_id)
        if not pub_record:
            raise ItemNotFoundError("Publication record not found.")

        if pub_record.mission_id != mission_id:
            raise MismatchError("Publication record mission ID mismatch.")

        queue_item = self.repository.get_publishing_queue_item(pub_record.queue_item_id)
        if not queue_item:
            raise ItemNotFoundError("Publishing queue item not found.")

        if queue_item.mission_id != mission_id:
            raise MismatchError("Publishing queue item mission ID mismatch.")
        if queue_item.queue_item_id != pub_record.queue_item_id:
            raise MismatchError("Publication queue item identity mismatch.")
        if queue_item.destination != pub_record.destination:
            raise MismatchError("Publication destination mismatch.")
        if queue_item.manifest_hash != pub_record.content_hash:
            raise MismatchError("Publication content hash mismatch.")

        if queue_item.status != PublishingQueueStatus.PUBLISHED_CONFIRMED:
            raise ConflictingDecisionError("Publication is not confirmed.")

        payload_hash = self._generate_payload_hash(metrics)

        existing = self.repository.find_observation_snapshot(publication_id, observed_at)
        if existing:
            if existing.payload_hash == payload_hash:
                return existing
            raise ConflictingDecisionError("Conflicting analytics evidence for the same observation time.")

        snapshot = AnalyticsSnapshot(
            mission_id=mission_id,
            publication_id=publication_id,
            queue_item_id=queue_item.queue_item_id,
            destination=pub_record.destination,
            observed_at=observed_at,
            imported_at=now,
            imported_by_actor=imported_by_actor,
            payload_hash=payload_hash,
            metrics=metrics,
        )

        try:
            with self.repository.transaction():
                self.repository.save_analytics_snapshot(snapshot)

                event = EventRecord(
                    mission_id=mission_id,
                    task_id=None,
                    event_type="analytics.snapshot_imported",
                    payload={
                        "analytics_snapshot_id": str(snapshot.analytics_snapshot_id),
                        "mission_id": str(mission_id),
                        "publication_id": str(publication_id),
                        "queue_item_id": str(snapshot.queue_item_id),
                        "destination": snapshot.destination,
                        "observed_at": observed_at.isoformat(),
                        "imported_at": now.isoformat(),
                        "actor": imported_by_actor,
                        "payload_hash": payload_hash,
                    },
                )
                self.repository.append_event(event)
        except DuplicateRecordError:
            winner = self.repository.find_observation_snapshot(publication_id, observed_at)
            if not winner:
                raise RepositoryConsistencyError("Expected duplicate snapshot but none found.")
            if winner.payload_hash == payload_hash:
                return winner
            raise ConflictingDecisionError("Conflicting analytics evidence for the same observation time.")

        return snapshot

    def interpret_analytics_snapshot(
        self,
        *,
        mission_id: UUID,
        analytics_snapshot_id: UUID,
        interpreted_by_actor: str,
        ruleset_version: str = RULESET_VERSION,
    ) -> AnalyticsInterpretation:
        """Generate and durably store one deterministic interpretation."""

        if not interpreted_by_actor.strip():
            raise MalformedCommandError("An actor must be specified.")
        if ruleset_version not in SUPPORTED_RULESETS:
            raise MalformedCommandError(
                f"Unsupported analytics interpretation ruleset: {ruleset_version}"
            )
        mission = self.repository.get_mission(mission_id)
        if mission is None:
            raise ItemNotFoundError("Mission not found.")
        snapshot = self.repository.find_snapshot_by_id(analytics_snapshot_id)
        if snapshot is None:
            raise ItemNotFoundError("Analytics snapshot not found.")
        if snapshot.mission_id != mission_id:
            raise MismatchError("Analytics snapshot mission ID mismatch.")
        publication = self.repository.get_publication_record_by_id(
            snapshot.publication_id
        )
        if publication is None:
            raise ItemNotFoundError("Publication record not found.")
        if publication.mission_id != mission_id:
            raise MismatchError("Publication record mission ID mismatch.")
        queue_item = self.repository.get_publishing_queue_item(
            snapshot.queue_item_id
        )
        if queue_item is None:
            raise ItemNotFoundError("Publishing queue item not found.")
        if queue_item.mission_id != mission_id:
            raise MismatchError("Publishing queue item mission ID mismatch.")
        if publication.queue_item_id != snapshot.queue_item_id:
            raise MismatchError("Snapshot publication queue identity mismatch.")
        if queue_item.queue_item_id != publication.queue_item_id:
            raise MismatchError("Publication queue identity mismatch.")
        if snapshot.destination != publication.destination:
            raise MismatchError("Snapshot publication destination mismatch.")
        if snapshot.destination != queue_item.destination:
            raise MismatchError("Snapshot queue destination mismatch.")
        if publication.content_hash != queue_item.manifest_hash:
            raise MismatchError("Publication content identity mismatch.")

        payload = build_interpretation_payload(
            snapshot,
            ruleset_version=ruleset_version,
        )
        payload_hash = interpretation_payload_hash(payload)
        existing = self.repository.find_snapshot_ruleset_interpretation(
            analytics_snapshot_id,
            ruleset_version,
        )
        if existing is not None:
            if existing.payload_hash == payload_hash:
                return existing
            raise ConflictingDecisionError(
                "Stored analytics interpretation conflicts with deterministic output."
            )

        interpreted_at = utc_now()
        interpretation = AnalyticsInterpretation(
            mission_id=mission_id,
            publication_id=snapshot.publication_id,
            queue_item_id=snapshot.queue_item_id,
            analytics_snapshot_id=analytics_snapshot_id,
            destination=snapshot.destination,
            interpreted_at=interpreted_at,
            interpreted_by_actor=interpreted_by_actor.strip(),
            ruleset_version=ruleset_version,
            overall_classification=payload.overall_classification,
            confidence=payload.confidence,
            metric_interpretations=payload.metric_interpretations,
            strengths=payload.strengths,
            weaknesses=payload.weaknesses,
            missing_evidence=payload.missing_evidence,
            summary=payload.summary,
            payload_hash=payload_hash,
        )
        try:
            with self.repository.transaction():
                self.repository.save_analytics_interpretation(interpretation)
                self.repository.append_event(
                    EventRecord(
                        mission_id=mission_id,
                        event_type="analytics.interpreted",
                        payload={
                            "analytics_interpretation_id": str(
                                interpretation.analytics_interpretation_id
                            ),
                            "analytics_snapshot_id": str(analytics_snapshot_id),
                            "mission_id": str(mission_id),
                            "publication_id": str(snapshot.publication_id),
                            "queue_item_id": str(snapshot.queue_item_id),
                            "destination": snapshot.destination,
                            "ruleset_version": ruleset_version,
                            "overall_classification": (
                                interpretation.overall_classification.value
                            ),
                            "confidence": interpretation.confidence.value,
                            "interpreted_at": interpreted_at.isoformat(),
                            "actor": interpretation.interpreted_by_actor,
                            "payload_hash": payload_hash,
                        },
                    )
                )
        except DuplicateRecordError:
            winner = self.repository.find_snapshot_ruleset_interpretation(
                analytics_snapshot_id,
                ruleset_version,
            )
            if winner is None:
                raise RepositoryConsistencyError(
                    "Expected duplicate interpretation but no winner exists."
                )
            if winner.payload_hash == payload_hash:
                return winner
            raise ConflictingDecisionError(
                "Concurrent analytics interpretation conflicts with deterministic output."
            )
        return interpretation

    def create_mission_lesson(
        self,
        *,
        mission_id: UUID,
        analytics_interpretation_id: UUID,
        created_by_actor: str,
        lesson_ruleset_version: str = LESSON_RULESET_VERSION,
    ) -> MissionLesson:
        """Create one deterministic lesson from a durable interpretation."""

        actor = created_by_actor.strip()
        if not actor:
            raise MalformedCommandError("An actor must be specified.")
        if lesson_ruleset_version not in SUPPORTED_LESSON_RULESETS:
            raise MalformedCommandError(
                f"Unsupported mission lesson ruleset: {lesson_ruleset_version}"
            )
        mission = self.repository.get_mission(mission_id)
        if mission is None:
            raise ItemNotFoundError("Mission not found.")
        interpretation = self.repository.find_interpretation_by_id(
            analytics_interpretation_id
        )
        if interpretation is None:
            raise ItemNotFoundError("Analytics interpretation not found.")
        if interpretation.mission_id != mission_id:
            raise MismatchError("Analytics interpretation mission ID mismatch.")
        snapshot = self.repository.find_snapshot_by_id(
            interpretation.analytics_snapshot_id
        )
        if snapshot is None:
            raise ItemNotFoundError("Analytics snapshot not found.")
        publication = self.repository.get_publication_record_by_id(
            interpretation.publication_id
        )
        if publication is None:
            raise ItemNotFoundError("Publication record not found.")
        queue_item = self.repository.get_publishing_queue_item(
            interpretation.queue_item_id
        )
        if queue_item is None:
            raise ItemNotFoundError("Publishing queue item not found.")

        identities = (
            snapshot.mission_id == mission_id,
            publication.mission_id == mission_id,
            queue_item.mission_id == mission_id,
            snapshot.publication_id == interpretation.publication_id,
            snapshot.queue_item_id == interpretation.queue_item_id,
            publication.queue_item_id == interpretation.queue_item_id,
            snapshot.destination == interpretation.destination,
            publication.destination == interpretation.destination,
            queue_item.destination == interpretation.destination,
            publication.content_hash == queue_item.manifest_hash,
        )
        if not all(identities):
            raise MismatchError(
                "Mission lesson source identity chain is inconsistent."
            )

        authoritative_payload = build_interpretation_payload(
            snapshot,
            ruleset_version=interpretation.ruleset_version,
        )
        if (
            interpretation_payload_hash(authoritative_payload)
            != interpretation.payload_hash
        ):
            raise StaleContentError(
                "Stored analytics interpretation is not authoritative."
            )
        authoritative_fields = {
            "overall_classification": (
                authoritative_payload.overall_classification
            ),
            "confidence": authoritative_payload.confidence,
            "metric_interpretations": (
                authoritative_payload.metric_interpretations
            ),
            "strengths": authoritative_payload.strengths,
            "weaknesses": authoritative_payload.weaknesses,
            "missing_evidence": authoritative_payload.missing_evidence,
            "summary": authoritative_payload.summary,
        }
        if any(
            getattr(interpretation, name) != value
            for name, value in authoritative_fields.items()
        ):
            raise StaleContentError(
                "Stored analytics interpretation content is inconsistent."
            )

        payload = build_mission_lesson_payload(
            interpretation,
            lesson_ruleset_version=lesson_ruleset_version,
        )
        payload_hash = mission_lesson_payload_hash(payload)
        existing = self.repository.find_interpretation_ruleset_lesson(
            analytics_interpretation_id,
            lesson_ruleset_version,
        )
        if existing is not None:
            if existing.payload_hash == payload_hash:
                return existing
            raise ConflictingDecisionError(
                "Stored mission lesson conflicts with deterministic output."
            )

        created_at = utc_now()
        lesson = MissionLesson(
            mission_id=mission_id,
            publication_id=interpretation.publication_id,
            queue_item_id=interpretation.queue_item_id,
            analytics_snapshot_id=interpretation.analytics_snapshot_id,
            analytics_interpretation_id=analytics_interpretation_id,
            destination=interpretation.destination,
            lesson_ruleset_version=lesson_ruleset_version,
            created_at=created_at,
            created_by_actor=actor,
            payload_hash=payload_hash,
            confidence=payload.confidence,
            summary=payload.summary,
            findings=payload.findings,
            evidence_references=payload.evidence_references,
            strengths=payload.strengths,
            weaknesses=payload.weaknesses,
            unknowns=payload.unknowns,
        )
        try:
            with self.repository.transaction():
                self.repository.save_mission_lesson(lesson)
                self.repository.append_event(
                    EventRecord(
                        mission_id=mission_id,
                        event_type="analytics.lesson_created",
                        payload={
                            "mission_lesson_id": str(
                                lesson.mission_lesson_id
                            ),
                            "analytics_interpretation_id": str(
                                analytics_interpretation_id
                            ),
                            "analytics_snapshot_id": str(
                                interpretation.analytics_snapshot_id
                            ),
                            "publication_id": str(
                                interpretation.publication_id
                            ),
                            "queue_item_id": str(
                                interpretation.queue_item_id
                            ),
                            "mission_id": str(mission_id),
                            "destination": interpretation.destination,
                            "lesson_ruleset_version": lesson_ruleset_version,
                            "confidence": lesson.confidence.value,
                            "created_at": created_at.isoformat(),
                            "actor": actor,
                            "payload_hash": payload_hash,
                        },
                    )
                )
        except DuplicateRecordError:
            winner = self.repository.find_interpretation_ruleset_lesson(
                analytics_interpretation_id,
                lesson_ruleset_version,
            )
            if winner is None:
                raise RepositoryConsistencyError(
                    "Expected duplicate mission lesson but no winner exists."
                )
            if winner.payload_hash == payload_hash:
                return winner
            raise ConflictingDecisionError(
                "Concurrent mission lesson conflicts with deterministic output."
            )
        return lesson

    def create_mission_recommendation(
        self,
        *,
        mission_id: UUID,
        mission_lesson_id: UUID,
        created_by_actor: str,
        recommendation_ruleset_version: str = (
            RECOMMENDATION_RULESET_VERSION
        ),
    ) -> MissionRecommendation:
        """Create one deterministic advisory recommendation."""

        actor = created_by_actor.strip()
        if not actor:
            raise MalformedCommandError("An actor must be specified.")
        if (
            recommendation_ruleset_version
            not in SUPPORTED_RECOMMENDATION_RULESETS
        ):
            raise MalformedCommandError(
                "Unsupported mission recommendation ruleset."
            )
        mission = self.repository.get_mission(mission_id)
        if mission is None:
            raise ItemNotFoundError("Mission not found.")
        lesson = self.repository.find_mission_lesson_by_id(mission_lesson_id)
        if lesson is None:
            raise ItemNotFoundError("Mission lesson not found.")
        if lesson.mission_id != mission_id:
            raise MismatchError("Mission lesson mission ID mismatch.")
        interpretation = self.repository.find_interpretation_by_id(
            lesson.analytics_interpretation_id
        )
        snapshot = self.repository.find_snapshot_by_id(
            lesson.analytics_snapshot_id
        )
        publication = self.repository.get_publication_record_by_id(
            lesson.publication_id
        )
        queue_item = self.repository.get_publishing_queue_item(
            lesson.queue_item_id
        )
        if interpretation is None:
            raise ItemNotFoundError("Analytics interpretation not found.")
        if snapshot is None:
            raise ItemNotFoundError("Analytics snapshot not found.")
        if publication is None:
            raise ItemNotFoundError("Publication record not found.")
        if queue_item is None:
            raise ItemNotFoundError("Publishing queue item not found.")
        if not all((
            interpretation.mission_id == mission_id,
            snapshot.mission_id == mission_id,
            publication.mission_id == mission_id,
            queue_item.mission_id == mission_id,
            interpretation.analytics_snapshot_id
            == lesson.analytics_snapshot_id,
            interpretation.publication_id == lesson.publication_id,
            interpretation.queue_item_id == lesson.queue_item_id,
            snapshot.publication_id == lesson.publication_id,
            snapshot.queue_item_id == lesson.queue_item_id,
            publication.queue_item_id == lesson.queue_item_id,
            interpretation.destination == lesson.destination,
            snapshot.destination == lesson.destination,
            publication.destination == lesson.destination,
            queue_item.destination == lesson.destination,
            publication.content_hash == queue_item.manifest_hash,
        )):
            raise MismatchError(
                "Mission recommendation source identity chain is inconsistent."
            )
        authoritative_lesson = build_mission_lesson_payload(
            interpretation,
            lesson_ruleset_version=lesson.lesson_ruleset_version,
        )
        if (
            mission_lesson_payload_hash(authoritative_lesson)
            != lesson.payload_hash
        ):
            raise StaleContentError("Mission lesson is not authoritative.")
        lesson_fields = {
            "confidence": authoritative_lesson.confidence,
            "summary": authoritative_lesson.summary,
            "findings": authoritative_lesson.findings,
            "evidence_references": authoritative_lesson.evidence_references,
            "strengths": authoritative_lesson.strengths,
            "weaknesses": authoritative_lesson.weaknesses,
            "unknowns": authoritative_lesson.unknowns,
        }
        if any(
            getattr(lesson, name) != value
            for name, value in lesson_fields.items()
        ):
            raise StaleContentError("Mission lesson content is inconsistent.")

        payload = build_mission_recommendation_payload(
            lesson,
            recommendation_ruleset_version=recommendation_ruleset_version,
        )
        payload_hash = mission_recommendation_payload_hash(payload)
        existing = self.repository.find_lesson_ruleset_recommendation(
            mission_lesson_id,
            recommendation_ruleset_version,
        )
        if existing:
            if existing.payload_hash == payload_hash:
                return existing
            raise ConflictingDecisionError(
                "Stored mission recommendation conflicts with deterministic "
                "output."
            )
        created_at = utc_now()
        recommendation = MissionRecommendation(
            mission_id=mission_id,
            publication_id=lesson.publication_id,
            queue_item_id=lesson.queue_item_id,
            analytics_snapshot_id=lesson.analytics_snapshot_id,
            analytics_interpretation_id=lesson.analytics_interpretation_id,
            mission_lesson_id=mission_lesson_id,
            destination=lesson.destination,
            recommendation_ruleset_version=recommendation_ruleset_version,
            created_at=created_at,
            created_by_actor=actor,
            payload_hash=payload_hash,
            confidence=payload.confidence,
            summary=payload.summary,
            proposals=payload.proposals,
            rationale=payload.rationale,
            evidence_references=payload.evidence_references,
        )
        try:
            with self.repository.transaction():
                self.repository.save_mission_recommendation(recommendation)
                self.repository.append_event(EventRecord(
                    mission_id=mission_id,
                    event_type="analytics.recommendation_created",
                    payload={
                        "mission_recommendation_id": str(
                            recommendation.mission_recommendation_id
                        ),
                        "mission_lesson_id": str(mission_lesson_id),
                        "analytics_interpretation_id": str(
                            lesson.analytics_interpretation_id
                        ),
                        "analytics_snapshot_id": str(
                            lesson.analytics_snapshot_id
                        ),
                        "mission_id": str(mission_id),
                        "publication_id": str(lesson.publication_id),
                        "queue_item_id": str(lesson.queue_item_id),
                        "destination": lesson.destination,
                        "recommendation_ruleset_version": (
                            recommendation_ruleset_version
                        ),
                        "confidence": recommendation.confidence.value,
                        "created_at": created_at.isoformat(),
                        "actor": actor,
                        "payload_hash": payload_hash,
                    },
                ))
        except DuplicateRecordError:
            winner = self.repository.find_lesson_ruleset_recommendation(
                mission_lesson_id,
                recommendation_ruleset_version,
            )
            if winner is None:
                raise RepositoryConsistencyError(
                    "Expected duplicate recommendation but no winner exists."
                )
            if winner.payload_hash == payload_hash:
                return winner
            raise ConflictingDecisionError(
                "Concurrent recommendation conflicts with deterministic output."
            )
        return recommendation

    def review_mission_recommendation(
        self,
        *,
        mission_id: UUID,
        mission_recommendation_id: UUID,
        decision: RecommendationDecision,
        decided_by_actor: str,
        founder_note: str | None = None,
    ) -> MissionRecommendation:
        """Persist one final founder review without executing it."""

        actor = decided_by_actor.strip()
        if not actor:
            raise MalformedCommandError("An actor must be specified.")
        note = founder_note.strip() if founder_note else None
        if note and len(note) > 2000:
            raise MalformedCommandError("Founder note is too long.")
        target = (
            RecommendationStatus.ACCEPTED
            if decision == RecommendationDecision.ACCEPT
            else RecommendationStatus.REJECTED
        )
        with self.repository.transaction():
            current = self.repository.find_mission_recommendation_by_id(
                mission_recommendation_id
            )
            if current is None:
                raise ItemNotFoundError("Mission recommendation not found.")
            if current.mission_id != mission_id:
                raise MismatchError("Mission recommendation mission ID mismatch.")
            if self.repository.get_mission(mission_id) is None:
                raise ItemNotFoundError("Mission not found.")
            if current.status != RecommendationStatus.PENDING:
                if (
                    current.status == target
                    and current.decided_by == actor
                    and current.founder_note == note
                ):
                    return current
                raise ConflictingDecisionError(
                    "Mission recommendation already has a final review."
                )
            decided_at = utc_now()
            updated = MissionRecommendation.model_validate({
                **current.model_dump(),
                "status": target,
                "decided_at": decided_at,
                "decided_by": actor,
                "founder_note": note,
            })
            self.repository.update_mission_recommendation(updated)
            self.repository.append_event(EventRecord(
                mission_id=mission_id,
                event_type="analytics.recommendation_reviewed",
                payload={
                    "mission_recommendation_id": str(
                        mission_recommendation_id
                    ),
                    "mission_id": str(mission_id),
                    "previous_status": RecommendationStatus.PENDING.value,
                    "new_status": target.value,
                    "decided_at": decided_at.isoformat(),
                    "decided_by": actor,
                    "reason_provided": bool(note),
                },
            ))
            return updated

class DepartmentBus:
    """Synchronous injected bus; it never starts background or external work."""
    def __init__(self) -> None: self.handlers: dict[str, Callable[[DepartmentCommand], DepartmentResult]] = {}
    def register(self, department, handler): self.handlers[department.value] = handler
    def dispatch(self, command: DepartmentCommand) -> DepartmentResult:
        handler=self.handlers.get(command.department.value)
        if handler is None: raise ValueError("No injected department handler is registered.")
        return handler(command)
