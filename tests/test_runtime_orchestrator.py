"""Tests for the high-level runtime orchestrator."""

import pytest

from agents.executive import AuraCOO
from agents.base_employee import BaseEmployee
from core import (
    DepartmentName,
    MissionRecord,
    OperationResult,
    StorageError,
    TaskRecord,
    ValidationError,
)
from runtime_engine.event_bus import RuntimeEventBus
from runtime_engine.mission_runner import MissionRunner
from runtime_engine.models import RuntimeMode
from runtime_engine.orchestrator import RuntimeOrchestrator
from runtime_engine.state_manager import RuntimeStateManager


class OrchestratorEmployee(BaseEmployee):
    def __init__(self) -> None:
        super().__init__(
            name="Orchestrator Worker",
            job_title="Research Worker",
            department=DepartmentName.RESEARCH,
        )

    def perform_task(self, task: TaskRecord) -> OperationResult:
        return OperationResult.ok("Orchestrated task completed.")


def build_orchestrator():
    bus = RuntimeEventBus()
    state = RuntimeStateManager(bus)
    runner = MissionRunner(state, bus)
    orchestrator = RuntimeOrchestrator(
        bus,
        state,
        AuraCOO(),
        runner,
        [OrchestratorEmployee()],
    )
    return orchestrator


def build_mission(*, approved: bool = True) -> MissionRecord:
    mission = MissionRecord(
        title="Orchestrated mission",
        description="Coordinate an approved deterministic mission.",
        lead_department=DepartmentName.RESEARCH,
    )
    mission.add_objective(description="Complete orchestration test.")
    if approved:
        mission.approve("Approved for runtime orchestration.")
    return mission


def test_runtime_and_employee_registration() -> None:
    orchestrator = build_orchestrator()
    orchestrator.start()
    assert orchestrator.snapshot().mode == RuntimeMode.RUNNING
    assert len(orchestrator.list_registered_employees()) == 1
    orchestrator.pause()
    orchestrator.resume()
    orchestrator.stop()
    assert orchestrator.snapshot().mode == RuntimeMode.STOPPED


def test_mission_validation_start_and_duplicate() -> None:
    orchestrator = build_orchestrator()
    orchestrator.start()
    with pytest.raises(ValidationError):
        orchestrator.start_mission(build_mission(approved=False))
    mission = build_mission()
    workflow = orchestrator.start_mission(mission)
    assert workflow.workflow_id in mission.workflow_ids
    with pytest.raises(StorageError):
        orchestrator.start_mission(mission)
    snapshot = orchestrator.snapshot()
    assert snapshot.missions and snapshot.workflows and snapshot.employees
    assert snapshot.recent_events


def test_pause_resume_and_stopped_runtime_blocking() -> None:
    orchestrator = build_orchestrator()
    orchestrator.start()
    mission = build_mission()
    orchestrator.start_mission(mission)
    orchestrator.run_next_mission_step(mission.mission_id)
    orchestrator.pause_mission(mission.mission_id)
    orchestrator.resume_mission(mission.mission_id)
    orchestrator.stop()
    with pytest.raises(ValidationError):
        orchestrator.run_next_mission_step(mission.mission_id)
