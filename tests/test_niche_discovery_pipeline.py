"""Tests for the deterministic Niche Discovery Pipeline v1."""

from datetime import datetime

import pytest

from agents.directors import ResearchDirector, StrategyDirector
from agents.executive import AuraCEO, AuraCOO
from agents.specialists import TrendHunter
from company_missions.fixtures import create_sample_niche_discovery_input
from company_missions.models import (
    NicheCandidateInput,
    NicheDiscoveryInput,
    NicheDiscoveryResult,
)
from company_missions.niche_discovery import NicheDiscoveryPipeline
from core import (
    DecisionOutcome,
    DecisionRecord,
    DecisionType,
    DepartmentName,
    MissionStatus,
    OperationResult,
    TaskRecord,
)
from marketing import MarketingDirector
from runtime_engine.event_bus import RuntimeEventBus
from runtime_engine.mission_runner import MissionRunner
from runtime_engine.models import RuntimeEventType
from runtime_engine.orchestrator import RuntimeOrchestrator
from runtime_engine.state_manager import RuntimeStateManager


def build_pipeline(
    *,
    ceo: AuraCEO | None = None,
    trend_hunter: TrendHunter | None = None,
):
    bus = RuntimeEventBus()
    state = RuntimeStateManager(bus)
    coo = AuraCOO()
    runner = MissionRunner(state, bus)
    orchestrator = RuntimeOrchestrator(bus, state, coo, runner)
    pipeline = NicheDiscoveryPipeline(
        orchestrator=orchestrator,
        ceo=ceo or AuraCEO(),
        coo=coo,
        research_director=ResearchDirector(),
        trend_hunter=trend_hunter,
        strategy_director=StrategyDirector(),
        marketing_director=MarketingDirector(),
    )
    return pipeline, orchestrator


def test_input_models_validate_scores_and_timestamps() -> None:
    candidate = create_sample_niche_discovery_input().candidate_niches[0]
    assert candidate.to_trend_candidate().name == candidate.name
    with pytest.raises(ValueError):
        NicheCandidateInput(
            name="Invalid",
            demand_score=101,
            trend_velocity_score=50,
            monetization_score=50,
            competition_score=50,
            production_difficulty_score=50,
        )


def test_successful_pipeline_uses_existing_employee_lifecycles() -> None:
    pipeline, orchestrator = build_pipeline(trend_hunter=TrendHunter())
    result = pipeline.run(
        create_sample_niche_discovery_input(),
        user_confirmed=True,
    )

    assert result.success is True
    discovery = NicheDiscoveryResult.model_validate(
        result.data["niche_discovery_result"]
    )
    assert discovery.selected_niche.name == (
        "AI productivity for small businesses"
    )
    assert discovery.marketing_readiness is True
    assert discovery.completed_at.tzinfo is not None
    assert {stage.stage_name for stage in discovery.stages} == {
        "executive_review",
        "research_planning",
        "trend_ranking",
        "strategy_planning",
        "marketing_planning",
    }
    snapshot = orchestrator.snapshot()
    assert snapshot.missions[0].status == MissionStatus.COMPLETED
    assert snapshot.workflows[0].progress_percentage == 100
    assert snapshot.decisions[0].outcome == DecisionOutcome.APPROVED
    assert orchestrator.event_bus.filter_by_type(
        RuntimeEventType.MISSION_COMPLETED
    )
    assert all(
        employee.current_task is None
        for employee in orchestrator.list_registered_employees()
    )
    assert discovery.model_dump(mode="json")


def test_explicit_confirmation_is_required() -> None:
    pipeline, orchestrator = build_pipeline(trend_hunter=TrendHunter())
    result = pipeline.run(create_sample_niche_discovery_input())

    assert result.success is False
    assert result.error_code == "USER_CONFIRMATION_REQUIRED"
    assert len(result.data["stages"]) == 1
    assert orchestrator.snapshot().workflows == []


class RejectingCEO(AuraCEO):
    def review_mission(self, mission) -> DecisionRecord:
        decision = DecisionRecord(
            title="Reject deterministic mission",
            decision_type=DecisionType.STRATEGIC,
            decision_maker_agent_id=self.agent_id,
            decision_maker_name=self.name,
            mission_id=mission.mission_id,
            department=DepartmentName.EXECUTIVE,
        )
        decision.decide(
            outcome=DecisionOutcome.REJECTED,
            reasoning="Rejected by deterministic test policy.",
            confidence_score=1.0,
        )
        return decision


def test_rejected_decision_stops_before_coo_execution() -> None:
    pipeline, orchestrator = build_pipeline(
        ceo=RejectingCEO(),
        trend_hunter=TrendHunter(),
    )
    result = pipeline.run(
        create_sample_niche_discovery_input(),
        user_confirmed=True,
    )
    assert result.error_code == "EXECUTIVE_APPROVAL_REQUIRED"
    assert orchestrator.snapshot().workflows == []


class FailingTrendHunter(TrendHunter):
    def perform_task(self, task: TaskRecord) -> OperationResult:
        return OperationResult.failure("Invalid deterministic specialist input.")


def test_empty_missing_and_specialist_failures_are_structured() -> None:
    missing, _ = build_pipeline(trend_hunter=None)
    assert missing.run(
        create_sample_niche_discovery_input(), user_confirmed=True
    ).error_code == "MISSING_EMPLOYEE_DEPENDENCY"

    pipeline, _ = build_pipeline(trend_hunter=TrendHunter())
    invalid = NicheDiscoveryInput.model_construct(
        **{
            **create_sample_niche_discovery_input().model_dump(),
            "candidate_niches": [],
        }
    )
    assert pipeline.run(invalid, user_confirmed=True).error_code == (
        "EMPTY_CANDIDATES"
    )

    failing, orchestrator = build_pipeline(trend_hunter=FailingTrendHunter())
    result = failing.run(
        create_sample_niche_discovery_input(), user_confirmed=True
    )
    assert result.success is False
    assert result.data["stages"][-1]["stage_name"] == "trend_ranking"
    assert orchestrator.snapshot().missions[0].status == MissionStatus.FAILED
