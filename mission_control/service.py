"""Mission lifecycle, approval, scheduling, recovery, and department bus."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import timedelta
from uuid import UUID

from core import utc_now
from mission_control.models import (
    ApprovalRequest, ApprovalState, ArtifactApprovalState, ArtifactRecord, DepartmentCommand, DepartmentResult,
    EventRecord, MissionControlProjection, MissionControlStatus, MissionRecord,
    RiskLevel, TaskRecord, TaskStatus,
)
from mission_control.repository import MissionControlRepository


TRANSITIONS = {
    MissionControlStatus.CREATED: {MissionControlStatus.READY, MissionControlStatus.CANCELLED},
    MissionControlStatus.READY: {MissionControlStatus.RUNNING, MissionControlStatus.PAUSED, MissionControlStatus.CANCELLED},
    MissionControlStatus.RUNNING: {MissionControlStatus.APPROVAL_REQUIRED, MissionControlStatus.BLOCKED, MissionControlStatus.PAUSED, MissionControlStatus.COMPLETED, MissionControlStatus.FAILED, MissionControlStatus.CANCELLED},
    MissionControlStatus.APPROVAL_REQUIRED: {MissionControlStatus.RUNNING, MissionControlStatus.BLOCKED, MissionControlStatus.CANCELLED},
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
    ) -> ArtifactRecord:
        """Register a deterministic logical artifact produced by one task."""

        self._mission(mission_id)
        self._task(task_id)
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
        artifact = ArtifactRecord(
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

    def dispatch(self, task_id: UUID) -> DepartmentCommand:
        task = self._task(task_id)
        if task.status == TaskStatus.COMPLETED:
            raise ValueError("Completed task dispatch would violate idempotency.")
        ready = {item.task_id for item in self.next_actions(task.mission_id)}
        if task_id not in ready:
            raise ValueError("Task is not the authoritative next action.")
        running = task.model_copy(update={"status": TaskStatus.RUNNING, "attempts": task.attempts + 1, "updated_at": utc_now()})
        self._update_task(running)
        self._event("task.dispatched", task.mission_id, task.task_id, {"attempt": running.attempts})
        return DepartmentCommand(mission_id=task.mission_id, task_id=task.task_id, department=task.department, operation=task.title, idempotency_key=task.idempotency_key)

    def accept_result(self, result: DepartmentResult) -> TaskRecord:
        task = self._task(result.task_id)
        if task.status == TaskStatus.COMPLETED:
            return task
        if task.status != TaskStatus.RUNNING:
            raise ValueError("Only a running task may accept a result.")
        status = TaskStatus.COMPLETED if result.success else (TaskStatus.RETRY_PENDING if task.attempts < task.maximum_attempts else TaskStatus.FAILED)
        updated = task.model_copy(update={"status": status, "blocking_reason": result.error_code, "updated_at": utc_now()})
        self._update_task(updated)
        self._event(
            "task.completed" if result.success else "task.failed",
            task.mission_id,
            task.task_id,
            {"title": task.title},
        )
        return updated

    def request_approval(self, task: TaskRecord, *, expires_in: timedelta = timedelta(hours=24)) -> ApprovalRequest:
        if not task.required_action or not task.required_artifact_hash:
            raise ValueError("Approval requires an action and content hash.")
        approval = ApprovalRequest(mission_id=task.mission_id, task_id=task.task_id, requested_action=task.required_action, risk=RiskLevel.CONSEQUENTIAL, content_hash=task.required_artifact_hash, expires_at=utc_now()+expires_in)
        self.repository.save_approval(approval)
        self._event("approval.requested", task.mission_id, task.task_id)
        return approval

    def decide_approval(self, approval_id: UUID, state: ApprovalState, *, approver: str, reason: str) -> ApprovalRequest:
        if state not in {ApprovalState.APPROVED, ApprovalState.REJECTED}:
            raise ValueError("Approval decisions may only approve or reject.")
        current = self._approval(approval_id)
        if current.state != ApprovalState.PENDING:
            raise ValueError("Only pending approval may be decided.")
        if current.expires_at <= utc_now():
            expired=current.model_copy(update={"state":ApprovalState.EXPIRED,"decided_at":utc_now()}); self.repository.save_approval(expired); raise ValueError("Approval has expired.")
        updated=current.model_copy(update={"state":state,"approver":approver,"reason":reason,"decided_at":utc_now()})
        self.repository.save_approval(updated); self._event(f"approval.{state.value}",current.mission_id,current.task_id); return updated

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
            status=TaskStatus.APPROVAL_REQUIRED if task.consequential else TaskStatus.RETRY_PENDING
            updated=task.model_copy(update={"status":status,"blocking_reason":"Interrupted process recovered; dispatch was not repeated.","updated_at":utc_now()})
            self._update_task(updated); self._event("task.interrupted",task.mission_id,task.task_id); recovered.append(updated)
        return recovered

    def replay(self, mission_id: UUID) -> list[EventRecord]:
        return self.repository.list_events(mission_id)

    def projection(self) -> MissionControlProjection:
        tasks=self.repository.list_tasks(); approvals=self.repository.list_approvals()
        artifacts = self.repository.list_artifacts()
        outcomes = [item.metadata for item in artifacts if item.artifact_type == "mission_learning.outcome"]
        lessons = [item.metadata for item in artifacts if item.artifact_type == "mission_learning.lesson"]
        pending_lessons = [item.metadata for item in artifacts if item.artifact_type == "mission_learning.lesson" and item.approval_state == ArtifactApprovalState.PENDING]
        influences = [mission.reasoning_summary for mission in self.repository.list_missions() if "Mission lessons changed" in mission.reasoning_summary]
        return MissionControlProjection(missions=self.repository.list_missions(),pending_approvals=[a for a in approvals if a.state==ApprovalState.PENDING],blocked_tasks=[t for t in tasks if t.status in {TaskStatus.BLOCKED,TaskStatus.APPROVAL_REQUIRED}],recent_events=self.repository.list_events()[-50:],artifacts=artifacts,recent_mission_outcomes=outcomes,generated_lessons=lessons,pending_lesson_approvals=pending_lessons,lesson_influences=influences,system_health="operational")

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


class DepartmentBus:
    """Synchronous injected bus; it never starts background or external work."""
    def __init__(self) -> None: self.handlers: dict[str, Callable[[DepartmentCommand], DepartmentResult]] = {}
    def register(self, department, handler): self.handlers[department.value] = handler
    def dispatch(self, command: DepartmentCommand) -> DepartmentResult:
        handler=self.handlers.get(command.department.value)
        if handler is None: raise ValueError("No injected department handler is registered.")
        return handler(command)
