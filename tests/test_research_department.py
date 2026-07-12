"""
Tests for AuraAI's Research Director and Trend Hunter.
"""

import pytest

from agents.directors import ResearchDirector
from agents.specialists import (
    TrendCandidate,
    TrendHunter,
)
from core import (
    DepartmentName,
    JobStatus,
    MissionRecord,
    TaskPriority,
    TaskRecord,
    ValidationError,
)


def build_research_mission() -> MissionRecord:
    """Create an approved research mission."""

    mission = MissionRecord(
        title="Research AuraAI's first profitable niche",
        description=(
            "Identify and validate sustainable niche opportunities "
            "for AuraAI's first creator business."
        ),
        priority=TaskPriority.HIGH,
        lead_department=DepartmentName.RESEARCH,
    )

    mission.add_objective(
        description="Produce a ranked niche shortlist.",
        success_metric="Three evidence-based niche candidates",
        target_value="3 shortlisted niches",
    )

    mission.approve(
        "Aura CEO approved the niche-research mission."
    )

    return mission


def build_candidates() -> list[TrendCandidate]:
    """Create deterministic trend candidates for testing."""

    return [
        TrendCandidate(
            name="AI productivity for small businesses",
            demand_score=88,
            trend_velocity_score=82,
            monetization_score=90,
            competition_score=55,
            production_difficulty_score=35,
            evidence=[
                "Strong practical business demand."
            ],
            risks=[
                "Requires accurate software demonstrations."
            ],
        ),
        TrendCandidate(
            name="General celebrity news",
            demand_score=95,
            trend_velocity_score=92,
            monetization_score=45,
            competition_score=95,
            production_difficulty_score=55,
            evidence=[
                "Large short-term audience."
            ],
            risks=[
                "Extremely competitive and news-dependent."
            ],
        ),
        TrendCandidate(
            name="Beginner personal finance education",
            demand_score=82,
            trend_velocity_score=65,
            monetization_score=88,
            competition_score=70,
            production_difficulty_score=50,
            evidence=[
                "Evergreen educational demand."
            ],
            risks=[
                "Financial claims require strict verification."
            ],
        ),
    ]


def test_research_director_creates_plan() -> None:
    """Create the trend, competitor, and audience assignments."""

    director = ResearchDirector()
    mission = build_research_mission()

    plan = director.create_research_plan(mission)

    assert plan.mission_id == mission.mission_id
    assert plan.assignment_count == 3
    assert plan.created_by_agent_id == director.agent_id

    roles = {
        assignment.specialist_role
        for assignment in plan.assignments
    }

    assert roles == {
        "Trend Hunter",
        "Research Analyst",
        "Audience Analyst",
    }

    generated_tasks = plan.to_task_records()

    assert len(generated_tasks) == 3
    assert all(
        task.department == DepartmentName.RESEARCH
        for task in generated_tasks
    )


def test_research_director_executes_employee_task() -> None:
    """Verify director execution through BaseEmployee."""

    director = ResearchDirector()
    mission = build_research_mission()

    task = TaskRecord(
        title="Prepare niche research plan",
        department=DepartmentName.RESEARCH,
        input_data={
            "mission": mission,
        },
    )

    director.accept_task(task)
    result = director.execute_current_task()

    assert result.success is True
    assert task.status == JobStatus.COMPLETED
    assert len(
        result.data["research_plan"]["assignments"]
    ) == 3
    assert len(
        result.data["generated_tasks"]
    ) == 3

    director.clear_current_task()

    assert director.current_task is None


def test_trend_hunter_ranks_candidates() -> None:
    """Rank candidate opportunities transparently."""

    hunter = TrendHunter()
    opportunities = hunter.rank_candidates(
        build_candidates()
    )

    assert len(opportunities) == 3
    assert opportunities[0].rank == 1
    assert (
        opportunities[0].name
        == "AI productivity for small businesses"
    )

    assert opportunities[0].opportunity_score > (
        opportunities[1].opportunity_score
    )

    assert (
        sum(
            opportunities[0].score_breakdown.values()
        )
        == opportunities[0].opportunity_score
    )


def test_trend_hunter_executes_employee_task() -> None:
    """Verify Trend Hunter through BaseEmployee lifecycle."""

    hunter = TrendHunter()

    task = TaskRecord(
        title="Rank niche opportunities",
        department=DepartmentName.RESEARCH,
        input_data={
            "candidates": build_candidates(),
        },
    )

    hunter.accept_task(task)
    result = hunter.execute_current_task()

    assert result.success is True
    assert task.status == JobStatus.COMPLETED
    assert result.data["candidate_count"] == 3
    assert (
        result.data["recommended_candidate"]["name"]
        == "AI productivity for small businesses"
    )

    hunter.clear_current_task()

    assert hunter.current_task is None


def test_trend_hunter_rejects_empty_candidates() -> None:
    """Prevent meaningless ranking without candidate data."""

    hunter = TrendHunter()

    with pytest.raises(ValidationError):
        hunter.rank_candidates([])