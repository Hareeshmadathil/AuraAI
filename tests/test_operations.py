"""
Tests for AuraAI's COO operations layer.
"""

import pytest

from core import (
    DepartmentName,
    JobStatus,
    MissionRecord,
    StorageError,
    TaskPriority,
    ValidationError,
)
from operations import (
    OperationQueue,
    WorkflowPlanner,
)


def build_approved_mission(
    *,
    title: str,
    priority: TaskPriority = TaskPriority.NORMAL,
) -> MissionRecord:
    """Create an approved mission ready for operations."""

    mission = MissionRecord(
        title=title,
        description=(
            "Complete a defined AuraAI business objective."
        ),
        priority=priority,
        lead_department=DepartmentName.STRATEGY,
    )

    mission.add_objective(
        description="Complete the approved business objective.",
        success_metric="Objective verified by executive review",
        target_value="1 completed objective",
    )

    mission.approve("Approved for operational planning.")

    return mission


def test_operation_queue_orders_by_priority() -> None:
    """Critical missions must be processed before lower priorities."""

    queue = OperationQueue()

    normal_mission = build_approved_mission(
        title="Normal mission",
        priority=TaskPriority.NORMAL,
    )

    critical_mission = build_approved_mission(
        title="Critical mission",
        priority=TaskPriority.CRITICAL,
    )

    high_mission = build_approved_mission(
        title="High mission",
        priority=TaskPriority.HIGH,
    )

    queue.enqueue(normal_mission)
    queue.enqueue(critical_mission)
    queue.enqueue(high_mission)

    assert queue.count() == 3
    assert queue.peek() is critical_mission

    assert queue.dequeue() is critical_mission
    assert queue.dequeue() is high_mission
    assert queue.dequeue() is normal_mission
    assert queue.count() == 0


def test_operation_queue_rejects_unapproved_mission() -> None:
    """Only approved missions may enter COO operations."""

    queue = OperationQueue()

    mission = MissionRecord(
        title="Unapproved mission",
        description="This mission has not been approved.",
        lead_department=DepartmentName.STRATEGY,
    )

    mission.add_objective(
        description="Complete one objective."
    )

    with pytest.raises(ValidationError):
        queue.enqueue(mission)


def test_operation_queue_rejects_duplicate_mission() -> None:
    """Prevent duplicate mission execution."""

    queue = OperationQueue()
    mission = build_approved_mission(
        title="Duplicate queue test"
    )

    queue.enqueue(mission)

    with pytest.raises(StorageError):
        queue.enqueue(mission)


def test_workflow_planner_creates_executable_workflow() -> None:
    """Convert an approved mission into an ordered workflow."""

    planner = WorkflowPlanner()

    mission = build_approved_mission(
        title="Discover the first profitable niche",
        priority=TaskPriority.HIGH,
    )

    workflow = planner.create_workflow(mission)

    assert workflow.mission_id == mission.mission_id
    assert len(workflow.steps) == 3
    assert workflow.status == JobStatus.CREATED

    workflow.start()

    ready_steps = workflow.get_ready_steps()

    assert len(ready_steps) == 1
    assert ready_steps[0].name == (
        "Prepare mission execution plan"
    )

    workflow.start_step(ready_steps[0].step_id)

    workflow.complete_step(
        ready_steps[0].step_id,
        output_data={
            "plan_prepared": True,
        },
    )

    second_step = workflow.get_ready_steps()[0]

    assert second_step.name == "Execute mission objectives"


def test_workflow_planner_requires_objectives() -> None:
    """Do not create workflows for undefined missions."""

    planner = WorkflowPlanner()

    mission = MissionRecord(
        title="Undefined mission",
        description="This mission has no measurable objectives.",
        lead_department=DepartmentName.STRATEGY,
        requires_user_approval=False,
    )

    with pytest.raises(ValidationError):
        planner.create_plan(mission)