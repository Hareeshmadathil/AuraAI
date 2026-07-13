"""Tests for bounded deterministic mission workflow execution."""

from agents.base_employee import BaseEmployee
from core import (
    DepartmentName,
    JobStatus,
    MissionRecord,
    OperationResult,
    TaskRecord,
)
from runtime_engine.event_bus import RuntimeEventBus
from runtime_engine.mission_runner import MissionRunner
from runtime_engine.models import RuntimeEventType
from runtime_engine.state_manager import RuntimeStateManager
from workflows import BaseWorkflow


class TestEmployee(BaseEmployee):
    __test__ = False

    def __init__(self, *, fail: bool = False) -> None:
        super().__init__(
            name="Deterministic Worker",
            job_title="Test Worker",
            department=DepartmentName.RESEARCH,
        )
        self.fail = fail

    def perform_task(self, task: TaskRecord) -> OperationResult:
        if self.fail:
            return OperationResult.failure("Deterministic failure.")
        return OperationResult.ok("Deterministic success.", data={"done": True})


class TestWorkflow(BaseWorkflow):
    __test__ = False

    def __init__(self, *, approval: bool = False, steps: int = 1) -> None:
        self.approval = approval
        self.step_total = steps
        super().__init__(name="Runtime test workflow")

    def build_steps(self) -> None:
        previous = None
        for index in range(self.step_total):
            step = self.add_step(
                name=f"Step {index + 1}",
                department=DepartmentName.RESEARCH,
                dependency_step_ids=[previous.step_id] if previous else [],
                requires_approval=self.approval and index == 0,
            )
            previous = step


def build_mission() -> MissionRecord:
    mission = MissionRecord(
        title="Runner mission",
        description="Execute deterministic workflow tests.",
        lead_department=DepartmentName.RESEARCH,
    )
    mission.add_objective(description="Complete test workflow.")
    mission.approve("Approved for test execution.")
    return mission


def build_runner(*employees, maximum_steps: int = 100):
    bus = RuntimeEventBus()
    state = RuntimeStateManager(bus)
    runner = MissionRunner(state, bus, employees, maximum_steps=maximum_steps)
    return runner, state, bus


def test_executes_step_and_preserves_employee_lifecycle() -> None:
    employee = TestEmployee()
    runner, state, bus = build_runner(employee)
    mission, workflow = build_mission(), TestWorkflow()

    result = runner.run_next_step(mission, workflow)

    assert result.success is True
    assert workflow.status == JobStatus.COMPLETED
    assert employee.current_task is None
    assert state.get_workflow_state(workflow.workflow_id).progress_percentage == 100
    assert state.get_mission_state(mission.mission_id).progress_percentage == 100
    assert bus.filter_by_type(RuntimeEventType.TASK_COMPLETED)


def test_missing_employee_and_approval_stop_safely() -> None:
    runner, _, _ = build_runner()
    unavailable = runner.run_next_step(build_mission(), TestWorkflow())
    assert unavailable.success is False
    assert unavailable.error_code == "EMPLOYEE_UNAVAILABLE"

    employee = TestEmployee()
    runner, _, _ = build_runner(employee)
    approval = runner.run_next_step(
        build_mission(), TestWorkflow(approval=True)
    )
    assert approval.error_code == "APPROVAL_REQUIRED"


def test_maximum_steps_and_employee_failure() -> None:
    runner, _, _ = build_runner(TestEmployee(), maximum_steps=1)
    limited = runner.run_workflow(build_mission(), TestWorkflow(steps=2))
    assert limited.error_code == "MAXIMUM_STEPS_REACHED"

    failing = TestEmployee(fail=True)
    runner, state, bus = build_runner(failing)
    mission, workflow = build_mission(), TestWorkflow()
    result = runner.run_next_step(mission, workflow)
    assert result.success is False
    assert workflow.status == JobStatus.FAILED
    assert state.get_mission_state(mission.mission_id).error_message
    assert bus.filter_by_type(RuntimeEventType.TASK_FAILED)
