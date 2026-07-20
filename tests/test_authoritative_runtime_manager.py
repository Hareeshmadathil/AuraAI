"""Phase 1 tests for the canonical runtime and employee dispatcher."""

from pathlib import Path

from agents.base_employee import BaseEmployee
from agents.employee_registry import EmployeeRegistry
from core import DepartmentName, OperationResult, TaskRecord as EmployeeTask
from mission_control import MissionControlStatus, MissionRecord, TaskRecord, TaskStatus
from runtime_engine import EmployeeDispatcher, create_persistent_runtime_manager


class ResearchEmployee(BaseEmployee):
    """Deterministic employee used to verify canonical dispatch."""

    def __init__(self) -> None:
        super().__init__(
            name="Phase One Researcher",
            job_title="Phase One Researcher",
            department=DepartmentName.RESEARCH,
        )
        self.last_received_input_data = {}

    def perform_task(self, task: EmployeeTask) -> OperationResult:
        self.last_received_input_data = task.input_data
        return OperationResult.ok(
            "Research completed.",
            data={"received_mission_id": task.input_data["mission_id"]},
        )


def build_manager(tmp_path: Path):
    registry = EmployeeRegistry()
    registry.register(ResearchEmployee())
    return create_persistent_runtime_manager(
        database_path=tmp_path / "mission-control.db",
        allowed_root=tmp_path,
        employee_dispatcher=EmployeeDispatcher(registry),
    )


def test_runtime_executes_only_the_mission_control_next_action(tmp_path: Path) -> None:
    manager = build_manager(tmp_path)
    mission = manager.mission_control.create_mission(
        MissionRecord(
            title="Canonical phase one mission",
            objective="Verify one authoritative execution path.",
            founder_owner="Founder",
        )
    )
    manager.mission_control.transition(mission.mission_id, MissionControlStatus.READY)
    manager.mission_control.transition(mission.mission_id, MissionControlStatus.RUNNING)
    first = manager.mission_control.add_task(
        TaskRecord(
            mission_id=mission.mission_id,
            title="Research first",
            department=DepartmentName.RESEARCH,
            idempotency_key=f"{mission.mission_id}:research:first",
        )
    )
    second = manager.mission_control.add_task(
        TaskRecord(
            mission_id=mission.mission_id,
            title="Research second",
            department=DepartmentName.RESEARCH,
            dependencies=[first.task_id],
            idempotency_key=f"{mission.mission_id}:research:second",
        )
    )

    assert manager.run_next(mission.mission_id).task_id == first.task_id
    assert manager.run_next(mission.mission_id).task_id == second.task_id
    assert manager.run_next(mission.mission_id) is None
    assert all(
        task.status == TaskStatus.COMPLETED
        for task in manager.mission_control.repository.list_tasks(mission.mission_id)
    )


def test_persistent_manager_reads_the_same_authoritative_state(tmp_path: Path) -> None:
    manager = build_manager(tmp_path)
    mission = manager.mission_control.create_mission(
        MissionRecord(
            title="Persistent phase one mission",
            objective="Survive runtime manager reconstruction.",
            founder_owner="Founder",
        )
    )

    reconstructed = build_manager(tmp_path)

    stored = reconstructed.mission_control.repository.get_mission(mission.mission_id)
    assert stored == mission
    assert reconstructed.mission_control.projection().missions == [mission]


def test_canonical_task_immutability(tmp_path: Path) -> None:
    manager = build_manager(tmp_path)
    mission = manager.mission_control.create_mission(
        MissionRecord(
            title="Immutability mission",
            objective="Verify task payload is not mutated.",
            founder_owner="Founder",
        )
    )
    manager.mission_control.transition(mission.mission_id, MissionControlStatus.READY)
    manager.mission_control.transition(mission.mission_id, MissionControlStatus.RUNNING)
    task = manager.mission_control.add_task(
        TaskRecord(
            mission_id=mission.mission_id,
            title="Research task",
            department=DepartmentName.RESEARCH,
            payload={"original_key": "original_value"},
            idempotency_key=f"{mission.mission_id}:research:immutability",
        )
    )
    
    # We can inspect what was dispatched by reading the attempt or just verify the DB
    manager.run_next(mission.mission_id)
    
    # Read the task from the database
    stored_task = manager.mission_control.repository.get_task(task.task_id)
    
    # The stored payload must be exactly the same, no attempt_id leaked into it
    assert stored_task.payload == {"original_key": "original_value"}
    assert "attempt_id" not in stored_task.payload
    
    # Retrieve the registered employee to check what it received
    registry = manager.employee_dispatcher._registry
    employee = registry.find_by_role("Phase One Researcher")
    
    assert employee.last_received_input_data["original_key"] == "original_value"
    assert "attempt_id" in employee.last_received_input_data
