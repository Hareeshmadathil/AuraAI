"""Dashboard integration tests for the niche discovery demonstration."""

from fastapi.testclient import TestClient

from app.main import create_app
from app.dashboard.service import DashboardService
from company_missions.niche_discovery import (
    create_niche_discovery_demo_dashboard_service,
)


def test_niche_discovery_runtime_maps_to_dashboard() -> None:
    service = create_niche_discovery_demo_dashboard_service()
    snapshot = service.build_snapshot()

    assert snapshot.mode.value == "demo"
    assert "DETERMINISTIC SAMPLE DATA" in snapshot.data_label
    assert snapshot.employees
    assert snapshot.missions[0].status.value == "completed"
    assert snapshot.workflows[0].progress_percentage == 100
    assert any(
        "AI productivity for small businesses" in event.detail
        for event in snapshot.activity
    )
    assert snapshot.system_health.status.value == "healthy"


def test_niche_discovery_dashboard_is_visibly_sample_data() -> None:
    client = TestClient(
        create_app(
            dashboard_service=create_niche_discovery_demo_dashboard_service()
        )
    )
    response = client.get("/")
    assert response.status_code == 200
    assert "DEMO DATA" in response.text
    assert "NICHE DISCOVERY DEMO" in response.text
    assert "AI productivity for small businesses" in response.text


def test_empty_dashboard_mode_remains_unaffected() -> None:
    snapshot = DashboardService().build_snapshot()
    assert snapshot.mode.value == "empty"
    assert snapshot.missions == []
