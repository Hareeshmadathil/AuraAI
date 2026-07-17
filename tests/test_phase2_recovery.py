"""Focused Phase 2 durable recovery, attempt, checkpoint, and retry tests."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from agents.base_employee import BaseEmployee
from agents.employee_registry import EmployeeRegistry
from app.main import create_runtime_app
from core import DepartmentName, OperationResult, TaskRecord as EmployeeTask
from mission_control import (
    ApprovalState,
    AttemptStatus,
    CheckpointKind,
    CheckpointResumability,
    FailureClassification,
    InMemoryMissionControlRepository,
    MissionControlService,
    MissionControlStatus,
    MissionRecord,
    SQLiteMissionControlRepository,
    TaskRecord,
    TaskStatus,
)
from runtime_engine.employee_dispatcher import EmployeeDispatcher
from runtime_engine.recovery import (
    RecoveryClassification,
    RecoveryGate,
    RecoveryGateState,
    RestartReconciler,
    build_recovery_projection,
)
from runtime_engine.runtime_manager import MissionRuntimeManager


class SequenceEmployee(BaseEmployee):
    """Employee returning deterministic results while inspecting attempts."""

    def __init__(self, control: MissionControlService, results=None) -> None:
        super().__init__(
            name="Recovery Worker",
            job_title=f"Recovery Worker {uuid4()}",
            department=DepartmentName.RESEARCH,
        )
        self.control = control
        self.results = list(results or [OperationResult.ok("done")])
        self.attempt_seen_before_execution = False

    def perform_task(self, task: EmployeeTask) -> OperationResult:
        self.attempt_seen_before_execution = any(
            item.task_id == task.task_id and item.status == AttemptStatus.STARTED
            for item in self.control.list_attempts()
        )
        return self.results.pop(0)


def build_runtime(results=None):
    control = MissionControlService(InMemoryMissionControlRepository())
    registry = EmployeeRegistry()
    employee = SequenceEmployee(control, results)
    registry.register(employee)
    gate = RecoveryGate()
    manager = MissionRuntimeManager(
        control,
        EmployeeDispatcher(registry),
        gate,
        RestartReconciler(control),
    )
    manager.reconcile()
    mission = manager.create_mission(MissionRecord(
        title="Phase 2 mission",
        objective="Test safe durable execution.",
        founder_owner="Founder",
    ))
    control.transition(mission.mission_id, MissionControlStatus.READY)
    control.transition(mission.mission_id, MissionControlStatus.RUNNING)
    return control, manager, gate, employee, mission


def add_task(control, mission, employee, **changes):
    values = {
        "mission_id": mission.mission_id,
        "title": "Durable task",
        "department": DepartmentName.RESEARCH,
        "assigned_agent_id": employee.agent_id,
        "idempotency_key": f"{mission.mission_id}:{uuid4()}",
    }
    values.update(changes)
    return control.add_task(TaskRecord(**values))


def test_attempt_is_durable_before_employee_and_finishes_successfully():
    control, manager, _, employee, mission = build_runtime()
    task = add_task(control, mission, employee)

    completed = manager.run_next(mission.mission_id)
    attempt = control.list_attempts(mission.mission_id)[0]

    assert employee.attempt_seen_before_execution
    assert completed.task_id == task.task_id
    assert attempt.status == AttemptStatus.COMPLETED
    assert attempt.result_reference
    assert control.accept_result  # successful acceptance remains centralized


def test_reconciliation_interrupts_attempt_without_dispatch_and_is_idempotent():
    control, manager, gate, employee, mission = build_runtime()
    task = add_task(control, mission, employee)
    preview = control.dispatch_preview(task.task_id)
    attempt = control.begin_attempt(
        task.task_id, employee.agent_id, correlation_id=preview.command_id
    )
    control.dispatch(task.task_id, command_id=preview.command_id)
    employee.results = [OperationResult.failure("must not run")]

    first = manager.reconcile()
    event_count = len(control.list_events())
    second = manager.reconcile()

    assert control.get_attempt(attempt.attempt_id).status == AttemptStatus.INTERRUPTED
    assert control.get_task(task.task_id).status == TaskStatus.RETRY_PENDING
    assert employee.results  # reconciliation never dispatched
    assert any(item.classification == RecoveryClassification.INTERRUPTED for item in first.findings)
    assert not any(item.classification == RecoveryClassification.INTERRUPTED for item in second.findings)
    assert len(control.list_events()) == event_count + 1  # second report only
    assert gate.state == RecoveryGateState.READY


def test_inconsistent_startup_fails_closed_but_projection_is_readable():
    control = MissionControlService(InMemoryMissionControlRepository())
    mission = control.create_mission(MissionRecord(
        title="Unsafe mission", objective="No active work", founder_owner="Founder"
    ))
    control.transition(mission.mission_id, MissionControlStatus.READY)
    control.transition(mission.mission_id, MissionControlStatus.RUNNING)
    gate = RecoveryGate()
    manager = MissionRuntimeManager(
        control, EmployeeDispatcher(EmployeeRegistry()), gate, RestartReconciler(control)
    )

    report = manager.reconcile()

    assert not report.safe_to_execute
    assert gate.state == RecoveryGateState.BLOCKED
    with pytest.raises(RuntimeError):
        manager.create_mission(MissionRecord(
            title="Blocked", objective="Must fail closed", founder_owner="Founder"
        ))
    assert build_recovery_projection(control, gate).gate_state == RecoveryGateState.BLOCKED


def test_checkpoint_integrity_ownership_and_non_completion():
    control, _, _, employee, mission = build_runtime()
    task = add_task(control, mission, employee)
    attempt = control.begin_attempt(task.task_id, employee.agent_id, correlation_id=uuid4())
    checkpoint = control.create_checkpoint(
        attempt_id=attempt.attempt_id,
        kind=CheckpointKind.PROGRESS,
        payload={"offset": 12},
        producer_employee_id=employee.agent_id,
        resumability=CheckpointResumability.RESUMABLE,
    )

    assert control.get_checkpoint(checkpoint.checkpoint_id) == checkpoint
    assert control.get_task(task.task_id).status == TaskStatus.PENDING
    with pytest.raises(ValueError):
        control.create_checkpoint(
            attempt_id=attempt.attempt_id,
            kind=CheckpointKind.PROGRESS,
            payload={"offset": 13},
            producer_employee_id=employee.agent_id,
            resumability=CheckpointResumability.RESUMABLE,
            expected_hash="a" * 64,
        )
    with pytest.raises(ValueError):
        control.create_checkpoint(
            attempt_id=attempt.attempt_id,
            kind=CheckpointKind.PROGRESS,
            payload={},
            producer_employee_id=uuid4(),
            resumability=CheckpointResumability.RESUMABLE,
        )


def test_retry_is_bounded_and_creates_an_immutable_new_attempt():
    control, manager, _, employee, mission = build_runtime([
        OperationResult.failure("temporary", retryable=True),
        OperationResult.ok("recovered"),
    ])
    task = add_task(control, mission, employee, maximum_attempts=2)

    failed = manager.run_next(mission.mission_id)
    first_attempt = control.list_attempts()[0]
    retried = manager.retry_task(mission.mission_id, task.task_id)
    attempts = control.list_attempts()

    assert failed.status == TaskStatus.RETRY_PENDING
    assert first_attempt.status == AttemptStatus.FAILED
    assert first_attempt.failure_classification == FailureClassification.RETRYABLE
    assert retried.status == TaskStatus.COMPLETED
    assert len(attempts) == 2
    assert attempts[0] == first_attempt
    with pytest.raises(ValueError):
        manager.retry_task(mission.mission_id, task.task_id)


def test_non_retryable_and_exhausted_failures_remain_blocked():
    control, manager, _, employee, mission = build_runtime([
        OperationResult.failure("permanent", retryable=False),
    ])
    task = add_task(control, mission, employee, maximum_attempts=1)

    failed = manager.run_next(mission.mission_id)

    assert failed.status == TaskStatus.FAILED
    assert failed.last_failure_classification == FailureClassification.EXHAUSTED
    with pytest.raises(ValueError):
        manager.retry_task(mission.mission_id, task.task_id)


def test_controlled_resume_validates_checkpoint_and_creates_new_attempt():
    control, manager, _, employee, mission = build_runtime([
        OperationResult.failure("interrupted", retryable=True),
        OperationResult.ok("resumed"),
    ])
    task = add_task(control, mission, employee, maximum_attempts=2)
    manager.run_next(mission.mission_id)
    first_attempt = control.list_attempts()[0]
    checkpoint = control.create_checkpoint(
        attempt_id=first_attempt.attempt_id,
        kind=CheckpointKind.EMPLOYEE_STATE,
        payload={"cursor": "safe"},
        producer_employee_id=employee.agent_id,
        resumability=CheckpointResumability.RESUMABLE,
    )

    resumed = manager.resume_task(
        mission.mission_id, task.task_id, checkpoint.checkpoint_id
    )

    assert resumed.status == TaskStatus.COMPLETED
    assert len(control.list_attempts()) == 2
    with pytest.raises(ValueError):
        manager.resume_task(mission.mission_id, task.task_id, checkpoint.checkpoint_id)


def test_founder_approval_survives_reconciliation_and_blocks_execution():
    control, manager, gate, employee, mission = build_runtime()
    task = add_task(
        control, mission, employee,
        consequential=True,
        required_action="approve_content",
        required_artifact_hash="a" * 64,
    )
    control.request_approval(task)
    control.transition(mission.mission_id, MissionControlStatus.APPROVAL_REQUIRED)

    report = manager.reconcile()

    assert gate.state == RecoveryGateState.READY
    assert any(item.founder_review_required for item in report.findings)
    assert control.list_approvals()[0].state == ApprovalState.PENDING
    with pytest.raises(ValueError):
        manager.run_next(mission.mission_id)


def test_normal_startup_reconciles_persisted_interruption(tmp_path: Path):
    database = tmp_path / "mission-control.db"
    repository = SQLiteMissionControlRepository(database, allowed_root=tmp_path)
    control = MissionControlService(repository)
    mission = control.create_mission(MissionRecord(
        title="Restart mission", objective="Recover after restart", founder_owner="Founder"
    ))
    control.transition(mission.mission_id, MissionControlStatus.READY)
    control.transition(mission.mission_id, MissionControlStatus.RUNNING)
    task = control.add_task(TaskRecord(
        mission_id=mission.mission_id,
        title="Interrupted",
        department=DepartmentName.RESEARCH,
        idempotency_key="restart:interrupted",
    ))
    preview = control.dispatch_preview(task.task_id)
    attempt = control.begin_attempt(task.task_id, uuid4(), correlation_id=preview.command_id)
    control.dispatch(task.task_id, command_id=preview.command_id)
    repository.connection.close()

    application = create_runtime_app(database_path=database, allowed_root=tmp_path)

    assert application.state.recovery_gate.state == RecoveryGateState.READY
    assert application.state.mission_control_service.get_attempt(attempt.attempt_id).status == AttemptStatus.INTERRUPTED
    assert application.state.mission_control_service.get_task(task.task_id).status == TaskStatus.RETRY_PENDING
    assert TestClient(application).get("/api/recovery").status_code == 200


def test_recovery_dashboard_projection_performs_no_writes():
    control, manager, gate, employee, mission = build_runtime()
    add_task(control, mission, employee)
    before = len(control.list_events())

    projection = build_recovery_projection(control, gate)

    assert projection.gate_state == RecoveryGateState.READY
    assert projection.tasks
    assert len(control.list_events()) == before


def test_normal_retry_endpoint_uses_shared_runtime_and_updates_dashboard(
    tmp_path: Path,
):
    application = create_runtime_app(
        database_path=tmp_path / "mission-control.db",
        allowed_root=tmp_path,
    )
    client = TestClient(application)
    response = client.post("/api/missions", json={
        "title": "API recovery mission",
        "objective": "Exercise explicit retry command.",
        "founder_owner": "Founder",
    })
    mission_id = response.json()["mission_id"]
    services = application.state.runtime_services
    control = services.mission_control_service
    mission = control.list_missions()[0]
    employee = SequenceEmployee(control, [
        OperationResult.failure("temporary", retryable=True),
        OperationResult.ok("retry complete"),
    ])
    services.employee_registry.register(employee)
    task = add_task(control, mission, employee, maximum_attempts=2)
    control.transition(mission.mission_id, MissionControlStatus.READY)
    control.transition(mission.mission_id, MissionControlStatus.RUNNING)

    assert client.post(f"/api/missions/{mission_id}/run-next").status_code == 200
    retried = client.post(
        f"/api/missions/{mission_id}/tasks/{task.task_id}/retry"
    )
    recovery = client.get("/api/recovery").json()
    dashboard = client.get("/api/dashboard").json()

    assert retried.status_code == 200
    assert len(control.list_attempts(mission.mission_id)) == 2
    assert recovery["tasks"][0]["attempt_count"] == 2
    assert dashboard["recovery"]["gate_state"] == "ready"


def test_commands_return_unavailable_while_gate_is_reconciling(tmp_path: Path):
    application = create_runtime_app(
        database_path=tmp_path / "mission-control.db",
        allowed_root=tmp_path,
    )
    application.state.recovery_gate.begin()

    response = TestClient(application).post("/api/missions", json={
        "title": "Blocked during recovery",
        "objective": "Must not enter canonical state.",
        "founder_owner": "Founder",
    })

    assert response.status_code == 503
    assert application.state.mission_control_service.list_missions() == []
