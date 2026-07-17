"""Deterministic restart reconciliation and shared execution gate."""

from __future__ import annotations

from enum import StrEnum
from datetime import datetime
from threading import RLock
from uuid import UUID, uuid4

from pydantic import Field

from core import AuraBaseModel, utc_now
from mission_control.models import (
    ApprovalState,
    AttemptStatus,
    MissionControlStatus,
    TaskStatus,
    FailureClassification,
)
from mission_control.service import MissionControlService


class RecoveryGateState(StrEnum):
    NOT_STARTED = "not_started"
    RECONCILING = "reconciling"
    READY = "ready"
    BLOCKED = "blocked"
    FAILED = "failed"


class RecoveryClassification(StrEnum):
    CLEAN = "clean"
    INTERRUPTED = "interrupted"
    RECOVERABLE = "recoverable"
    RETRYABLE = "retryable"
    AWAITING_FOUNDER = "awaiting_founder"
    DEPENDENCY_BLOCKED = "dependency_blocked"
    INCONSISTENT = "inconsistent"
    MANUAL_INTERVENTION_REQUIRED = "manual_intervention_required"


class RecoveryFinding(AuraBaseModel):
    finding_id: UUID = Field(default_factory=uuid4)
    mission_id: UUID
    task_id: UUID | None = None
    observed_state: str
    classification: RecoveryClassification
    recommended_action: str
    execution_blocked: bool
    founder_review_required: bool = False
    attempt_id: UUID | None = None
    checkpoint_id: UUID | None = None


class RecoveryReport(AuraBaseModel):
    report_id: UUID = Field(default_factory=uuid4)
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    findings: list[RecoveryFinding] = Field(default_factory=list)
    safe_to_execute: bool = False


class RecoveryGate:
    """One application-scoped fail-closed gate for mission commands."""

    def __init__(self) -> None:
        self._state = RecoveryGateState.NOT_STARTED
        self._report: RecoveryReport | None = None
        self._lock = RLock()

    @property
    def state(self) -> RecoveryGateState:
        return self._state

    @property
    def report(self) -> RecoveryReport | None:
        return self._report

    def begin(self) -> None:
        with self._lock:
            self._state = RecoveryGateState.RECONCILING

    def finish(self, report: RecoveryReport) -> None:
        with self._lock:
            self._report = report
            self._state = (
                RecoveryGateState.READY
                if report.safe_to_execute
                else RecoveryGateState.BLOCKED
            )

    def fail(self) -> None:
        with self._lock:
            self._state = RecoveryGateState.FAILED

    def require_ready(self) -> None:
        if self._state != RecoveryGateState.READY:
            raise RuntimeError(
                f"Mission execution unavailable: recovery gate is {self._state.value}."
            )


class TaskRecoveryView(AuraBaseModel):
    mission_id: UUID
    task_id: UUID
    status: TaskStatus
    attempt_count: int
    last_failure_classification: FailureClassification
    retry_eligible: bool
    retry_exhausted: bool
    checkpoint_available: bool
    resumability_status: str
    founder_review_required: bool
    recommended_action: str


class RecoveryStatusProjection(AuraBaseModel):
    gate_state: RecoveryGateState
    report: RecoveryReport | None = None
    interrupted_tasks: list[UUID] = Field(default_factory=list)
    tasks: list[TaskRecoveryView] = Field(default_factory=list)


def build_recovery_projection(
    control: MissionControlService,
    gate: RecoveryGate,
) -> RecoveryStatusProjection:
    """Build a write-free operational view from authoritative queries."""

    views: list[TaskRecoveryView] = []
    interrupted: list[UUID] = []
    for task in control.list_tasks():
        attempts = [
            item for item in control.list_attempts(task.mission_id)
            if item.task_id == task.task_id
        ]
        checkpoints = [
            item for item in control.list_checkpoints(task.mission_id)
            if item.task_id == task.task_id
        ]
        if task.status == TaskStatus.RUNNING or any(
            item.status == AttemptStatus.INTERRUPTED for item in attempts
        ):
            interrupted.append(task.task_id)
        resumability = (
            max(checkpoints, key=lambda item: item.sequence).resumability.value
            if checkpoints else "unavailable"
        )
        pending_approval = any(
            item.state == ApprovalState.PENDING
            and (item.task_id is None or item.task_id == task.task_id)
            for item in control.list_approvals(task.mission_id)
        )
        retry_exhausted = task.attempts >= task.maximum_attempts
        retry_eligible = (
            task.status == TaskStatus.RETRY_PENDING
            and not retry_exhausted
            and not pending_approval
        )
        action = (
            "founder_review" if pending_approval
            else "resume" if checkpoints and retry_eligible
            else "retry" if retry_eligible
            else "manual_intervention" if task.status in {TaskStatus.BLOCKED, TaskStatus.FAILED}
            else "none"
        )
        views.append(TaskRecoveryView(
            mission_id=task.mission_id,
            task_id=task.task_id,
            status=task.status,
            attempt_count=len(attempts),
            last_failure_classification=task.last_failure_classification,
            retry_eligible=retry_eligible,
            retry_exhausted=retry_exhausted,
            checkpoint_available=bool(checkpoints),
            resumability_status=resumability,
            founder_review_required=pending_approval,
            recommended_action=action,
        ))
    return RecoveryStatusProjection(
        gate_state=gate.state,
        report=gate.report,
        interrupted_tasks=interrupted,
        tasks=views,
    )


class RestartReconciler:
    """Inspect canonical state, apply minimal recovery, and never dispatch."""

    def __init__(self, mission_control: MissionControlService) -> None:
        self._control = mission_control

    def reconcile(self, mission_id: UUID | None = None) -> RecoveryReport:
        started = utc_now()
        findings: list[RecoveryFinding] = []
        missions = [
            mission for mission in self._control.list_missions()
            if mission_id is None or mission.mission_id == mission_id
        ]
        terminal = {
            MissionControlStatus.COMPLETED,
            MissionControlStatus.FAILED,
            MissionControlStatus.CANCELLED,
        }
        for mission in missions:
            if mission.status in terminal:
                continue
            findings.extend(self._inspect_mission(mission))

        # Mutate only interrupted process state after the complete inspection.
        active_attempts = [
            attempt for attempt in self._control.list_attempts(mission_id)
            if attempt.status == AttemptStatus.STARTED
        ]
        for attempt in active_attempts:
            self._control.interrupt_attempt(attempt.attempt_id)
        recovered_tasks = self._control.recover_interrupted()
        for task in recovered_tasks:
            if not any(item.task_id == task.task_id for item in findings):
                findings.append(RecoveryFinding(
                    mission_id=task.mission_id,
                    task_id=task.task_id,
                    observed_state=TaskStatus.RUNNING.value,
                    classification=RecoveryClassification.INTERRUPTED,
                    recommended_action="Explicit retry or checkpoint resume required.",
                    execution_blocked=True,
                ))

        unsafe = {
            RecoveryClassification.INCONSISTENT,
            RecoveryClassification.MANUAL_INTERVENTION_REQUIRED,
        }
        report = RecoveryReport(
            started_at=started,
            completed_at=utc_now(),
            findings=findings,
            safe_to_execute=not any(item.classification in unsafe for item in findings),
        )
        self._control.record_recovery_report(report)
        return report

    def _inspect_mission(self, mission) -> list[RecoveryFinding]:
        tasks = self._control.list_tasks(mission.mission_id)
        attempts = self._control.list_attempts(mission.mission_id)
        approvals = self._control.list_approvals(mission.mission_id)
        checkpoints = self._control.list_checkpoints(mission.mission_id)
        findings: list[RecoveryFinding] = []
        by_id = {task.task_id: task for task in tasks}
        for task in tasks:
            active_attempt = next((
                item for item in attempts
                if item.task_id == task.task_id
                and item.status == AttemptStatus.STARTED
            ), None)
            if task.status == TaskStatus.RUNNING or active_attempt is not None:
                latest_checkpoint = max(
                    (item for item in checkpoints if item.task_id == task.task_id),
                    key=lambda item: item.sequence,
                    default=None,
                )
                findings.append(RecoveryFinding(
                    mission_id=mission.mission_id,
                    task_id=task.task_id,
                    observed_state=task.status.value,
                    classification=RecoveryClassification.INTERRUPTED,
                    recommended_action="Validate checkpoint then explicitly resume or retry.",
                    execution_blocked=True,
                    attempt_id=active_attempt.attempt_id if active_attempt else None,
                    checkpoint_id=latest_checkpoint.checkpoint_id if latest_checkpoint else None,
                ))
            elif task.status == TaskStatus.RETRY_PENDING:
                findings.append(RecoveryFinding(
                    mission_id=mission.mission_id,
                    task_id=task.task_id,
                    observed_state=task.status.value,
                    classification=RecoveryClassification.RETRYABLE,
                    recommended_action="Wait for an explicit eligible retry command.",
                    execution_blocked=True,
                ))
            elif task.status == TaskStatus.APPROVAL_REQUIRED:
                findings.append(RecoveryFinding(
                    mission_id=mission.mission_id,
                    task_id=task.task_id,
                    observed_state=task.status.value,
                    classification=RecoveryClassification.AWAITING_FOUNDER,
                    recommended_action="Wait for the explicit founder decision.",
                    execution_blocked=True,
                    founder_review_required=True,
                ))
            elif task.status in {TaskStatus.FAILED, TaskStatus.BLOCKED}:
                findings.append(RecoveryFinding(
                    mission_id=mission.mission_id,
                    task_id=task.task_id,
                    observed_state=task.status.value,
                    classification=RecoveryClassification.MANUAL_INTERVENTION_REQUIRED,
                    recommended_action="Founder or operator intervention is required.",
                    execution_blocked=True,
                ))
            missing = [item for item in task.dependencies if item not in by_id]
            failed = [
                item for item in task.dependencies
                if item in by_id and by_id[item].status in {
                    TaskStatus.FAILED, TaskStatus.BLOCKED, TaskStatus.CANCELLED
                }
            ]
            if missing:
                findings.append(RecoveryFinding(
                    mission_id=mission.mission_id, task_id=task.task_id,
                    observed_state=task.status.value,
                    classification=RecoveryClassification.INCONSISTENT,
                    recommended_action="Repair missing dependency references manually.",
                    execution_blocked=True,
                ))
            elif failed:
                findings.append(RecoveryFinding(
                    mission_id=mission.mission_id, task_id=task.task_id,
                    observed_state=task.status.value,
                    classification=RecoveryClassification.DEPENDENCY_BLOCKED,
                    recommended_action="Resolve failed dependencies before retry.",
                    execution_blocked=True,
                ))
        pending_approval = any(
            item.state == ApprovalState.PENDING for item in approvals
        )
        if mission.status == MissionControlStatus.APPROVAL_REQUIRED or pending_approval:
            findings.append(RecoveryFinding(
                mission_id=mission.mission_id,
                observed_state=mission.status.value,
                classification=RecoveryClassification.AWAITING_FOUNDER,
                recommended_action="Wait for the explicit founder decision.",
                execution_blocked=True,
                founder_review_required=True,
            ))
        elif mission.status == MissionControlStatus.RUNNING and (
            not tasks or all(task.status == TaskStatus.COMPLETED for task in tasks)
        ):
            findings.append(RecoveryFinding(
                mission_id=mission.mission_id,
                observed_state=mission.status.value,
                classification=RecoveryClassification.INCONSISTENT,
                recommended_action="Founder review required: running mission has no tasks.",
                execution_blocked=True,
                founder_review_required=True,
            ))
        elif not findings:
            findings.append(RecoveryFinding(
                mission_id=mission.mission_id,
                observed_state=mission.status.value,
                classification=RecoveryClassification.CLEAN,
                recommended_action="No recovery action required.",
                execution_blocked=False,
            ))
        return findings
