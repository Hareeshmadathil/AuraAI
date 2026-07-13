"""Provider page and JSON projection tests."""

from fastapi.testclient import TestClient

from app.dashboard.service import DashboardService
from app.main import create_app
from providers import (
    DeterministicProvider,
    PromptCategory,
    ProviderCapability,
    ProviderRegistry,
    ProviderRouter,
    build_department_prompt,
)


def build_service() -> DashboardService:
    registry = ProviderRegistry()
    registry.register_provider(DeterministicProvider())
    router = ProviderRouter(registry)
    router.route(
        ProviderCapability.METADATA,
        build_department_prompt(
            "dashboard_metadata",
            PromptCategory.STRATEGY,
            "responsible creator workflows",
        ),
    )
    return DashboardService(provider_state=router.build_state())


def test_provider_page_shows_safe_status_and_usage() -> None:
    response = TestClient(create_app(dashboard_service=build_service())).get(
        "/providers"
    )
    assert response.status_code == 200
    assert "AI Provider Layer" in response.text
    assert "deterministic" in response.text
    assert "1 requests" in response.text


def test_dashboard_api_adds_provider_state_without_breaking_fields() -> None:
    response = TestClient(create_app(dashboard_service=build_service())).get(
        "/api/dashboard"
    )
    payload = response.json()
    assert payload["active_missions"] == 0
    assert payload["providers"]["usage"][0]["capability"] == "metadata"
    assert "text" not in payload["providers"]["usage"][0]


def test_empty_dashboard_provider_page_remains_safe() -> None:
    response = TestClient(create_app()).get("/providers")
    assert response.status_code == 200
    assert "No provider registry was supplied" in response.text
