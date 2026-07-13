"""Tests for explicit runtime projection state."""

from uuid import uuid4

import pytest

from core import (
    AgentIdentity,
    AgentStatus,
    DecisionRecord,
    DecisionType,
    DepartmentName,
    JobStatus,
    MissionRecord,
    StorageError,
    ValidationError,
    WorkflowRecord,
)
from runtime_engine.event_bus import RuntimeEventBus
from runtime_engine.models import RuntimeEventType, RuntimeMode
from runtime_engine.state_manager import RuntimeStateManager


def build_state_manager() -> RuntimeStateManager:
    return RuntimeStateManager(RuntimeEventBus())


def test_runtime_lifecycle() -> None:
    state = build_state_manager()
    state.start_runtime()
    assert state.mode == RuntimeMode.RUNNING
    state.pause_runtime()
    assert state.mode == RuntimeMode.PAUSED
    state.resume_runtime()
    state.stop_runtime()
    assert state.mode == RuntimeMode.STOPPED


def test_registration_updates_statistics_and_ordering() -> None:
    state = build_state_manager()
    employee = AgentIdentity(
        name="Test Planner",
        job_title="Test Planner",
        department=DepartmentName.STRATEGY,
        status=AgentStatus.IDLE,
    )
    mission = MissionRecord(
        title="Runtime mission",
        description="Exercise runtime projections.",
    )
    workflow = WorkflowRecord(name="Runtime workflow", status=JobStatus.RUNNING)
    decision = DecisionRecord(
        title="Runtime decision",
        decision_type=DecisionType.OPERATIONAL,
    )
    state.register_employee(employee)
    state.register_mission(mission)
    state.register_workflow(workflow)
    state.register_decision(decision)
    state.update_employee_state(employee.agent_id, status=AgentStatus.WORKING)

    statistics = state.build_statistics()
    snapshot = state.snapshot()
    assert statistics.registered_missions == 1
    assert statistics.registered_workflows == 1
    assert statistics.employees_working == 1
    assert statistics.pending_decisions == 1
    assert snapshot.employees[0].agent_id == employee.agent_id
    assert state.event_bus.filter_by_type(
        RuntimeEventType.EMPLOYEE_STATUS_CHANGED
    )


def test_duplicates_and_unknown_updates_are_rejected() -> None:
    state = build_state_manager()
    employee = AgentIdentity(
        name="Duplicate",
        job_title="Specialist",
        department=DepartmentName.RESEARCH,
    )
    state.register_employee(employee)
    with pytest.raises(StorageError):
        state.register_employee(employee)
    with pytest.raises(ValidationError):
        state.update_mission_state(uuid4(), progress_percentage=50)
