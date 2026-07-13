"""Gemini advice remains additive, safe, and vendor-neutral downstream."""

from fastapi.testclient import TestClient
from pydantic import SecretStr

from agents.directors import ResearchDirector
from app.dashboard.service import DashboardService
from app.main import create_app
from core import DepartmentName, MissionRecord, TaskRecord
from providers import ProviderCapability, create_provider_router
from providers.gemini import GeminiConfig, MockGeminiTransport
from runtime_engine import RuntimeEventBus, RuntimeStateManager
from tests.gemini_helpers import response_for


def build_mission() -> MissionRecord:
    mission = MissionRecord(
        title="Research a responsible creator niche",
        description="Use additive provider advice with deterministic planning.",
        lead_department=DepartmentName.RESEARCH,
    )
    mission.add_objective(
        description="Create one research plan.",
        success_metric="Validated plan",
        target_value="1",
    )
    mission.approve("Founder approved research planning, not publishing.")
    return mission


def build_router(event_bus=None):
    config = GeminiConfig(
        enabled=True,
        allow_live_requests=True,
        api_key=SecretStr("fake-dashboard-key"),
        maximum_retries=0,
    )
    return create_provider_router(
        config,
        MockGeminiTransport(lambda request: response_for(request)),
        event_bus=event_bus,
    )


def test_employee_accepts_gemini_advice_without_replacing_plan() -> None:
    director = ResearchDirector()
    director.configure_provider_router(build_router())
    task = TaskRecord(title="Research", input_data={"mission": build_mission()})
    director.accept_task(task)
    result = director.execute_current_task()

    assert result.success is True
    assert result.data["research_plan"]
    assert result.data["provider_advisory"]["provider"] == "gemini"
    assert "Gemini" not in result.data["research_plan"]["research_goal"]
    director.clear_current_task()
    assert director.current_task is None


def test_provider_failure_does_not_break_employee_lifecycle() -> None:
    router = create_provider_router(
        GeminiConfig(enabled=True),
        MockGeminiTransport(lambda request: response_for(request)),
    )
    director = ResearchDirector()
    director.configure_provider_router(router)
    director.accept_task(
        TaskRecord(title="Research", input_data={"mission": build_mission()})
    )
    result = director.execute_current_task()
    assert result.success is True
    assert result.data["provider_advisory"]["provider"] == "deterministic"


def test_runtime_and_dashboard_expose_only_safe_provider_metadata() -> None:
    bus = RuntimeEventBus()
    router = build_router(bus)
    router.route(
        ProviderCapability.RESEARCH,
        __import__("tests.gemini_helpers", fromlist=["prompt_for"]).prompt_for(
            ProviderCapability.RESEARCH
        ),
    )
    runtime = RuntimeStateManager(bus)
    runtime.update_provider_state(router.build_state())
    snapshot = runtime.snapshot()
    service = DashboardService(provider_state=snapshot.provider_state)
    client = TestClient(create_app(dashboard_service=service))
    payload = client.get("/api/dashboard").json()
    rendered = client.get("/providers")
    serialized = str(payload)

    assert rendered.status_code == 200
    assert "Google AI Pro consumer access" in rendered.text
    assert "fake-dashboard-key" not in serialized
    assert "user_prompt" not in serialized
    assert "response_body" not in serialized
    gemini = next(
        item for item in payload["providers"]["health"] if item["name"] == "gemini"
    )
    assert gemini["configured"] is True
    assert gemini["live_requests_allowed"] is True
    assert gemini["request_count"] == 1
