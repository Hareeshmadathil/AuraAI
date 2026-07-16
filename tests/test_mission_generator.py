"""Dynamic Mission Generation V1 tests."""
from pathlib import Path
from types import SimpleNamespace
from fastapi.testclient import TestClient

from agents.executive import AuraCEO
from agents.specialists.trend_hunter import TrendCandidate, TrendHunter
from company_missions.mission_generator import MissionGenerator
from company_missions.mission_zero_integration import MissionZeroIntegration
from app.main import create_app
from intelligence_director.service import IntelligenceDirectorService
from mission_control import (
    InMemoryMissionControlRepository,
    MissionControlService,
    MissionControlStatus,
    SQLiteMissionControlRepository,
    TaskStatus,
)


class KnowledgeStub:
    """Deterministic Knowledge Manager query boundary for generator tests."""

    def __init__(self, existing: set[str] | None = None) -> None:
        self.existing = {item.casefold() for item in existing or set()}

    def query(self, query):
        matches = []
        if query.text.casefold() in self.existing:
            matches.append(
                SimpleNamespace(
                    version=SimpleNamespace(
                        topic=SimpleNamespace(normalized_name=query.text)
                    )
                )
            )
        return SimpleNamespace(matches=matches)


def candidate(name: str, score: float) -> TrendCandidate:
    return TrendCandidate(
        name=name,
        demand_score=score,
        trend_velocity_score=score,
        monetization_score=score,
        competition_score=100-score,
        production_difficulty_score=100-score,
        evidence=["offline test"],
    )


def generator(repository, *, existing=None):
    control = MissionControlService(repository)
    value = MissionGenerator(
        control=control,
        trend_hunter=TrendHunter(),
        intelligence_director=IntelligenceDirectorService(),
        knowledge_manager=KnowledgeStub(existing),
        ceo=AuraCEO(),
    )
    return value, control


def stable_fields(value):
    return value.model_dump(exclude={"created_at", "updated_at"})


def test_generation_is_deterministic_and_stored():
    first_generator, first_control = generator(InMemoryMissionControlRepository())
    second_generator, _ = generator(InMemoryMissionControlRepository())

    first = first_generator.generate("Grow AuraAI.")
    second = second_generator.generate("Grow AuraAI.")

    assert stable_fields(first) == stable_fields(second)
    assert first_control.repository.get_mission(first.mission_id) == first
    assert first.founder_goal == "Grow AuraAI."
    assert first.offline_execution is True
    assert first.publishing_required is False
    assert first.rendering_required is False


def test_duplicate_candidates_and_known_missions_are_removed():
    value, _ = generator(
        InMemoryMissionControlRepository(), existing={"Highest"}
    )
    generated = value.generate(
        "Grow AuraAI.",
        candidates=[
            candidate("Highest", 95),
            candidate("Highest", 10),
            candidate("Novel", 70),
        ],
    )
    assert generated.title == "Novel"
    assert "no exact prior mission" in generated.reasoning_summary


def test_ranking_selects_highest_combined_opportunity():
    value, _ = generator(InMemoryMissionControlRepository())
    generated = value.generate(
        "Grow AuraAI.",
        candidates=[candidate("Lower", 40), candidate("Higher", 90)],
    )
    assert generated.title == "Higher"
    assert generated.mission_score > 70
    assert generated.priority.value == "high"


def test_generated_mission_executes_existing_pipeline_with_dependencies(tmp_path):
    repository = SQLiteMissionControlRepository(
        tmp_path / "mission-control.db", allowed_root=tmp_path
    )
    value, control = generator(repository)
    generated = value.generate("Grow AuraAI.")
    result = MissionZeroIntegration(
        control,
        project_root=Path(__file__).resolve().parents[1],
    ).run(generated)

    tasks = repository.list_tasks(generated.mission_id)
    assert result.projection.missions[0].status == MissionControlStatus.APPROVAL_REQUIRED
    assert result.projection.missions[0].founder_goal == "Grow AuraAI."
    assert sum(item.status == TaskStatus.COMPLETED for item in tasks) == 13
    assert all(
        not item.dependencies or item.dependencies == [tasks[index-1].task_id]
        for index, item in enumerate(tasks)
    )
    assert result.timeline[-1] == "Waiting For Founder Approval"
    client = TestClient(
        create_app(
            dashboard_service=result.dashboard_service,
            mission_control_service=control,
        )
    )
    dashboard_mission = client.get("/api/mission-control").json()["missions"][0]
    assert dashboard_mission["founder_goal"] == "Grow AuraAI."
    assert dashboard_mission["mission_score"] == generated.mission_score
    assert dashboard_mission["priority"] == generated.priority.value


def test_generation_and_execution_have_no_external_operations(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        raise AssertionError("External operation was attempted.")

    monkeypatch.setattr(
        "providers.gemini.transport.UnavailableGeminiTransport.send", forbidden
    )
    monkeypatch.setattr(
        "web_intelligence.service.WebIntelligenceService.execute", forbidden
    )
    repository = SQLiteMissionControlRepository(
        tmp_path / "mission-control.db", allowed_root=tmp_path
    )
    value, control = generator(repository)
    generated = value.generate("Grow AuraAI.")
    result = MissionZeroIntegration(
        control,
        project_root=Path(__file__).resolve().parents[1],
    ).run(generated)
    event_types = {item.event_type for item in control.replay(generated.mission_id)}
    assert not event_types & {
        "web_crawl_started",
        "browser_session_started",
        "provider_completed",
        "render_started",
        "publish_started",
    }
    assert result.approval_request.state.value == "pending"
