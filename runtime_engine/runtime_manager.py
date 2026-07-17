"""Authoritative runtime facade backed exclusively by Mission Control."""

from __future__ import annotations

from pathlib import Path
import hashlib
import json
from uuid import UUID

from mission_control.models import (
    MissionControlStatus,
    MissionRecord,
    TaskRecord,
    ApprovalState,
    CheckpointResumability,
    RetryMode,
    TaskStatus,
)
from mission_control.repository import SQLiteMissionControlRepository
from mission_control.service import MissionControlService
from runtime_engine.employee_dispatcher import EmployeeDispatcher
from runtime_engine.recovery import RecoveryGate, RestartReconciler


class MissionRuntimeManager:
    """Run canonical tasks without maintaining a second mission state store."""

    def __init__(
        self,
        mission_control: MissionControlService,
        employee_dispatcher: EmployeeDispatcher,
        recovery_gate: RecoveryGate | None = None,
        reconciler: RestartReconciler | None = None,
    ) -> None:
        self.mission_control = mission_control
        self.employee_dispatcher = employee_dispatcher
        self.recovery_gate = recovery_gate
        self.reconciler = reconciler

    def create_mission(self, mission: MissionRecord) -> MissionRecord:
        """Submit a new mission through the authoritative command boundary."""

        self._require_recovery_ready()
        if mission.status != MissionControlStatus.CREATED:
            raise ValueError("New missions must be submitted in created state.")
        return self.mission_control.create_mission(mission)

    def run_next(self, mission_id: UUID) -> TaskRecord | None:
        """Run the next authoritative task, or return ``None`` when none is ready."""

        self._require_recovery_ready()
        mission = self.mission_control.get_mission(mission_id)
        if mission is None:
            raise KeyError(f"Unknown mission: {mission_id}")
        if mission.status != MissionControlStatus.RUNNING:
            raise ValueError("Only a running mission may execute tasks.")
        self._require_no_pending_approval(mission_id)
        actions = self.mission_control.next_actions(mission_id)
        if not actions:
            return None
        return self._execute(actions[0])

    def _execute(self, task: TaskRecord) -> TaskRecord:
        preview = self.mission_control.dispatch_preview(task.task_id)
        employee = self.employee_dispatcher.resolve_employee(preview)
        attempt = self.mission_control.begin_attempt(
            task.task_id,
            employee.agent_id,
            correlation_id=preview.command_id,
        )
        command = self.mission_control.dispatch(
            task.task_id,
            command_id=preview.command_id,
        )
        result = self.employee_dispatcher.dispatch(command)
        accepted = self.mission_control.accept_result(result)
        self.mission_control.finish_attempt(attempt.attempt_id, result)
        return accepted

    def retry_task(self, mission_id: UUID, task_id: UUID) -> TaskRecord:
        """Explicitly retry one policy-eligible canonical task."""

        self._require_recovery_ready()
        mission = self._running_mission(mission_id)
        self._require_no_pending_approval(mission.mission_id)
        task = self.mission_control.get_task(task_id)
        if task is None or task.mission_id != mission_id:
            raise KeyError(f"Unknown mission task: {task_id}")
        if task.status != TaskStatus.RETRY_PENDING:
            raise ValueError("Only retry-pending tasks may be retried.")
        if task.retry_mode != RetryMode.EXPLICIT:
            raise ValueError("Task retry policy requires manual intervention.")
        if task.attempts >= task.maximum_attempts:
            raise ValueError("Task retry attempts are exhausted.")
        if task.next_eligible_at is not None and task.next_eligible_at > self._now():
            raise ValueError("Task retry delay has not elapsed.")
        return self._execute(task)

    def resume_task(
        self,
        mission_id: UUID,
        task_id: UUID,
        checkpoint_id: UUID | None = None,
    ) -> TaskRecord:
        """Explicitly continue with a valid checkpoint or restart policy."""

        self._require_recovery_ready()
        if checkpoint_id is not None:
            checkpoint = self.mission_control.get_checkpoint(checkpoint_id)
            if checkpoint is None:
                raise ValueError("Checkpoint does not exist.")
            if (checkpoint.mission_id, checkpoint.task_id) != (mission_id, task_id):
                raise ValueError("Checkpoint ownership does not match.")
            if checkpoint.schema_version != 1:
                raise ValueError("Checkpoint schema is incompatible.")
            if checkpoint.resumability != CheckpointResumability.RESUMABLE:
                raise ValueError("Checkpoint is not resumable.")
            attempt = self.mission_control.get_attempt(checkpoint.attempt_id)
            if attempt is None or (attempt.mission_id, attempt.task_id) != (
                mission_id, task_id
            ):
                raise ValueError("Checkpoint attempt correlation is invalid.")
            encoded = json.dumps(
                checkpoint.payload, sort_keys=True, separators=(",", ":"), default=str
            )
            if hashlib.sha256(encoded.encode("utf-8")).hexdigest() != checkpoint.payload_hash:
                raise ValueError("Checkpoint checksum is invalid.")
        return self.retry_task(mission_id, task_id)

    def reconcile(self, mission_id: UUID | None = None):
        """Run fail-closed reconciliation without dispatching work."""

        if self.recovery_gate is None or self.reconciler is None:
            raise RuntimeError("Runtime recovery is not configured.")
        self.recovery_gate.begin()
        try:
            report = self.reconciler.reconcile(mission_id)
        except Exception:
            self.recovery_gate.fail()
            raise
        self.recovery_gate.finish(report)
        return report

    def recover_interrupted(self) -> list[TaskRecord]:
        """Recover tasks left running by an interrupted process."""

        return self.mission_control.recover_interrupted()

    def _running_mission(self, mission_id: UUID) -> MissionRecord:
        mission = self.mission_control.get_mission(mission_id)
        if mission is None:
            raise KeyError(f"Unknown mission: {mission_id}")
        if mission.status != MissionControlStatus.RUNNING:
            raise ValueError("Only a running mission may execute tasks.")
        return mission

    def _require_no_pending_approval(self, mission_id: UUID) -> None:
        if any(
            item.state == ApprovalState.PENDING
            for item in self.mission_control.list_approvals(mission_id)
        ):
            raise ValueError("Mission is awaiting founder approval.")

    def _require_recovery_ready(self) -> None:
        if self.recovery_gate is not None:
            self.recovery_gate.require_ready()

    @staticmethod
    def _now():
        from core import utc_now

        return utc_now()


def create_persistent_runtime_manager(
    *,
    database_path: Path,
    allowed_root: Path,
    employee_dispatcher: EmployeeDispatcher,
) -> MissionRuntimeManager:
    """Compose the runtime with the free, durable SQLite state backend."""

    repository = SQLiteMissionControlRepository(
        database_path,
        allowed_root=allowed_root,
    )
    return MissionRuntimeManager(
        MissionControlService(repository),
        employee_dispatcher,
    )
