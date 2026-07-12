"""
Tests for AuraAI's Strategy Director.
"""

from agents.directors import StrategyDirector
from core import (
    DepartmentName,
    JobStatus,
    MissionRecord,
    TaskPriority,
    TaskRecord,
)


def build_strategy_mission() -> MissionRecord:
    """Create an approved mission ready for strategy planning."""

    mission = MissionRecord(
        title="Prepare AuraAI's first creator business",
        description=(
            "Select the niche, audience, brand positioning, "
            "monetization strategy, and social-platform launch plan."
        ),
        priority=TaskPriority.HIGH,
        lead_department=DepartmentName.STRATEGY,
    )

    mission.add_objective(
        description="Select one validated content niche.",
        success_metric="One niche approved by the user",
        target_value="1 approved niche",
    )

    mission.add_objective(
        description="Approve the final brand positioning.",
        success_metric="One approved positioning statement",
        target_value="1 approved brand position",
    )

    mission.approve(
        "Aura CEO approved the company-launch strategy mission."
    )

    return mission


def test_strategy_director_creates_complete_plan() -> None:
    """Create the six-part company launch strategy plan."""

    director = StrategyDirector()
    mission = build_strategy_mission()

    plan = director.create_strategy_plan(mission)

    assert plan.mission_id == mission.mission_id
    assert plan.created_by_agent_id == director.agent_id
    assert plan.work_item_count == 6

    departments = {
        item.department
        for item in plan.work_items
    }

    assert DepartmentName.RESEARCH in departments
    assert DepartmentName.REVENUE in departments
    assert DepartmentName.STRATEGY in departments
    assert DepartmentName.DISTRIBUTION in departments
    assert DepartmentName.EXECUTIVE in departments

    tasks = plan.to_task_records()

    assert len(tasks) == 6
    assert all(
        task.status == JobStatus.CREATED
        for task in tasks
    )


def test_strategy_director_executes_employee_task() -> None:
    """Verify strategy planning through BaseEmployee lifecycle."""

    director = StrategyDirector()
    mission = build_strategy_mission()

    task = TaskRecord(
        title="Create AuraAI company-launch strategy",
        department=DepartmentName.STRATEGY,
        input_data={
            "mission": mission,
        },
    )

    director.accept_task(task)
    result = director.execute_current_task()

    assert result.success is True
    assert task.status == JobStatus.COMPLETED

    strategy_data = result.data["strategy_plan"]

    assert strategy_data["mission_id"] == str(
        mission.mission_id
    )

    assert len(
        strategy_data["work_items"]
    ) == 6

    assert len(
        result.data["generated_tasks"]
    ) == 6

    director.clear_current_task()

    assert director.current_task is None


def test_strategy_plan_final_step_requires_approval() -> None:
    """The final launch recommendation must be user-approved."""

    director = StrategyDirector()
    mission = build_strategy_mission()

    plan = director.create_strategy_plan(mission)

    final_item = plan.work_items[-1]

    assert (
        final_item.title
        == "Submit the complete launch strategy for approval"
    )
    assert final_item.requires_user_approval is True
    assert final_item.department == DepartmentName.EXECUTIVE