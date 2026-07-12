"""Tests for AuraAI's Marketing Director foundation."""

import pytest
from pydantic import ValidationError as PydanticValidationError

from core import (
    ContentPlatform,
    DepartmentName,
    JobStatus,
    MissionRecord,
    TaskPriority,
    TaskRecord,
    ValidationError,
)
from marketing import MarketingDirector, MarketingPlan


def build_marketing_mission(*, approved: bool = True) -> MissionRecord:
    """Create a campaign mission for marketing planning tests."""

    mission = MissionRecord(
        title="Launch AuraAI's creator education campaign",
        description=(
            "Build audience awareness with useful content across the "
            "four supported social platforms."
        ),
        priority=TaskPriority.HIGH,
        lead_department=DepartmentName.MARKETING,
    )
    mission.add_objective(
        description="Publish a coordinated launch campaign.",
        success_metric="Approved platform campaign briefs",
        target_value="4 approved briefs",
    )

    if approved:
        mission.approve("Aura CEO approved marketing planning.")

    return mission


def test_marketing_director_creates_valid_plan() -> None:
    """Create a complete, structured marketing plan."""

    director = MarketingDirector()
    mission = build_marketing_mission()

    plan = director.create_marketing_plan(mission)

    assert plan.mission_id == mission.mission_id
    assert plan.created_by_agent_id == director.agent_id
    assert plan.brand_positioning
    assert plan.content_pillars
    assert plan.audience_promise
    assert plan.campaign_goals
    assert plan.expected_outputs

    tasks = plan.to_task_records()

    assert len(tasks) == 4
    assert all(task.status == JobStatus.CREATED for task in tasks)
    assert all(
        task.department == DepartmentName.MARKETING
        for task in tasks
    )


def test_marketing_director_uses_base_employee_lifecycle() -> None:
    """Execute marketing planning through BaseEmployee."""

    director = MarketingDirector()
    mission = build_marketing_mission()
    task = TaskRecord(
        title="Create launch marketing plan",
        department=DepartmentName.MARKETING,
        input_data={"mission": mission},
    )

    director.accept_task(task)
    result = director.execute_current_task()

    assert result.success is True
    assert task.status == JobStatus.COMPLETED
    assert len(result.data["generated_tasks"]) == 4
    assert result.data["marketing_plan"][
        "final_approval_required"
    ] is True

    director.clear_current_task()
    assert director.current_task is None


def test_marketing_director_rejects_unapproved_mission() -> None:
    """Reject a mission that has not received approval."""

    director = MarketingDirector()

    with pytest.raises(ValidationError):
        director.create_marketing_plan(
            build_marketing_mission(approved=False)
        )


def test_marketing_plan_has_expected_platform_assignments() -> None:
    """Assign a distinct campaign role to every required platform."""

    plan = MarketingDirector().create_marketing_plan(
        build_marketing_mission()
    )

    assert {
        assignment.platform
        for assignment in plan.platform_assignments
    } == {
        ContentPlatform.YOUTUBE,
        ContentPlatform.YOUTUBE_SHORTS,
        ContentPlatform.INSTAGRAM,
        ContentPlatform.TIKTOK,
    }
    assert all(
        assignment.platform_role
        and assignment.campaign_goal
        and assignment.expected_outputs
        for assignment in plan.platform_assignments
    )


def test_marketing_plan_requires_final_approval() -> None:
    """Prevent creation of a plan that bypasses final approval."""

    plan = MarketingDirector().create_marketing_plan(
        build_marketing_mission()
    )
    plan_data = plan.model_dump()
    plan_data["final_approval_required"] = False

    with pytest.raises(PydanticValidationError):
        MarketingPlan.model_validate(plan_data)
