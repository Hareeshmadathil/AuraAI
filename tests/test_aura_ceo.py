"""
Tests for Aura, the CEO of AuraAI Creator OS.
"""

from agents.executive import AuraCEO
from core import (
    DecisionOutcome,
    DepartmentName,
    JobStatus,
    MissionRecord,
    TaskPriority,
    TaskRecord,
)


def build_ready_mission() -> MissionRecord:
    """Create a complete mission ready for executive review."""

    mission = MissionRecord(
        title="Discover AuraAI's first profitable niche",
        description=(
            "Research and recommend a sustainable content niche, "
            "target audience, positioning, and monetization strategy."
        ),
        priority=TaskPriority.HIGH,
        lead_department=DepartmentName.STRATEGY,
    )

    mission.add_objective(
        description="Recommend one validated content niche.",
        success_metric="One niche approved by the user",
        target_value="1 approved niche",
    )

    mission.add_objective(
        description="Define the target audience.",
        success_metric="Complete audience profile",
        target_value="1 audience profile",
    )

    return mission


def test_aura_approves_ready_mission() -> None:
    """Approve a mission with objectives and department ownership."""

    aura = AuraCEO()
    mission = build_ready_mission()

    decision = aura.review_mission(mission)

    assert decision.outcome == DecisionOutcome.APPROVED
    assert decision.is_final is True
    assert decision.confidence_percentage == 97.0
    assert decision.mission_id == mission.mission_id
    assert decision.decision_maker_agent_id == aura.agent_id
    assert len(decision.evidence) == 1
    assert len(decision.next_actions) == 2


def test_aura_requests_research_for_undefined_mission() -> None:
    """Do not approve missions without measurable objectives."""

    aura = AuraCEO()

    mission = MissionRecord(
        title="Build a successful creator brand",
        description=(
            "Create a strong brand across several social platforms."
        ),
        lead_department=DepartmentName.STRATEGY,
    )

    decision = aura.review_mission(mission)

    assert (
        decision.outcome
        == DecisionOutcome.REQUIRES_RESEARCH
    )
    assert decision.confidence_percentage == 99.0
    assert len(decision.next_actions) == 2


def test_aura_requests_department_assignment() -> None:
    """Require ownership before creating a workflow."""

    aura = AuraCEO()

    mission = MissionRecord(
        title="Launch AuraAI's first channel",
        description=(
            "Create and launch the first validated content channel."
        ),
    )

    mission.add_objective(
        description="Publish the first approved video."
    )

    decision = aura.review_mission(mission)

    assert (
        decision.outcome
        == DecisionOutcome.REQUIRES_USER_INPUT
    )
    assert len(decision.next_actions) == 1


def test_aura_executes_mission_review_task() -> None:
    """Verify Aura through the complete BaseEmployee lifecycle."""

    aura = AuraCEO()
    mission = build_ready_mission()

    task = TaskRecord(
        title="Review first niche mission",
        department=DepartmentName.EXECUTIVE,
        input_data={
            "mission": mission,
        },
    )

    aura.accept_task(task)
    result = aura.execute_current_task()

    assert result.success is True
    assert task.status == JobStatus.COMPLETED

    decision_data = result.data["decision"]

    assert (
        decision_data["outcome"]
        == DecisionOutcome.APPROVED.value
    )
    assert (
        decision_data["decision_maker_name"]
        == "Aura"
    )

    aura.clear_current_task()

    assert aura.current_task is None