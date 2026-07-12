"""
Tests for AuraAI's Chief Operating Officer.
"""

import pytest

from agents.executive import AuraCOO
from core import (
    DepartmentName,
    JobStatus,
    MissionRecord,
    MissionStatus,
    TaskPriority,
    TaskRecord,
    ValidationError,
)


def build_approved_mission(
    *,
    title: str,
    priority: TaskPriority = TaskPriority.NORMAL,
) -> MissionRecord:
    """Create a mission ready for COO operations."""

    mission = MissionRecord(
        title=title,
        description=(
            "Complete a measurable AuraAI company objective."
        ),
        priority=priority,
        lead_department=DepartmentName.STRATEGY,
    )

    mission.add_objective(
        description="Complete the approved objective.",
        success_metric="Executive verification",
        target_value="1 completed objective",
    )

    mission.approve(
        "Aura CEO approved the mission."
    )

    return mission


def test_coo_coordinates_approved_mission() -> None:
    """Queue, plan, and link an approved mission."""

    coo = AuraCOO()

    mission = build_approved_mission(
        title="Discover AuraAI's first niche",
        priority=TaskPriority.HIGH,
    )

    workflow = coo.coordinate_mission(mission)

    assert workflow.mission_id == mission.mission_id
    assert workflow.status == JobStatus.CREATED
    assert len(workflow.steps) == 3

    assert mission.status == MissionStatus.PLANNING
    assert workflow.workflow_id in mission.workflow_ids

    assert coo.queued_mission_count == 0
    assert coo.active_workflow_count == 1

    stored_workflow = coo.get_active_workflow(
        str(workflow.workflow_id)
    )

    assert stored_workflow is workflow


def test_coo_processes_priority_queue() -> None:
    """Critical missions must be planned before normal missions."""

    coo = AuraCOO()

    normal_mission = build_approved_mission(
        title="Normal operational mission",
        priority=TaskPriority.NORMAL,
    )

    critical_mission = build_approved_mission(
        title="Critical operational mission",
        priority=TaskPriority.CRITICAL,
    )

    coo.queue_mission(normal_mission)
    coo.queue_mission(critical_mission)

    first_workflow = coo.plan_next_mission()

    assert (
        first_workflow.mission_id
        == critical_mission.mission_id
    )

    second_workflow = coo.plan_next_mission()

    assert (
        second_workflow.mission_id
        == normal_mission.mission_id
    )


def test_coo_executes_complete_employee_task() -> None:
    """Verify COO through the BaseEmployee lifecycle."""

    coo = AuraCOO()

    mission = build_approved_mission(
        title="Prepare AuraAI brand strategy",
    )

    task = TaskRecord(
        title="Coordinate approved brand mission",
        department=DepartmentName.EXECUTIVE,
        input_data={
            "operation": "coordinate_mission",
            "mission": mission,
        },
    )

    coo.accept_task(task)
    result = coo.execute_current_task()

    assert result.success is True
    assert task.status == JobStatus.COMPLETED

    assert (
        result.data["mission_id"]
        == str(mission.mission_id)
    )

    assert (
        result.data["workflow"]["step_count"]
        == 3
    )

    assert (
        result.data["workflow"]["status"]
        == JobStatus.CREATED.value
    )

    coo.clear_current_task()

    assert coo.current_task is None


def test_coo_rejects_unknown_operation() -> None:
    """Unsupported operational commands must fail safely."""

    coo = AuraCOO()

    task = TaskRecord(
        title="Unsupported COO request",
        department=DepartmentName.EXECUTIVE,
        input_data={
            "operation": "delete_company",
        },
    )

    coo.accept_task(task)
    result = coo.execute_current_task()

    assert result.success is False
    assert (
        result.error_code
        == "VALIDATION_ERROR"
    )
    assert task.status == JobStatus.FAILED


def test_coo_cannot_plan_unapproved_mission() -> None:
    """Direct COO operations must still enforce approval rules."""

    coo = AuraCOO()

    mission = MissionRecord(
        title="Unapproved mission",
        description=(
            "This mission has not received executive approval."
        ),
        lead_department=DepartmentName.STRATEGY,
    )

    mission.add_objective(
        description="Complete an objective."
    )

    with pytest.raises(ValidationError):
        coo.queue_mission(mission)