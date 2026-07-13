from fastapi.testclient import TestClient

from app.main import create_app, create_intelligence_demo_app
from company_missions.intelligence_analysis import (
    create_intelligence_demo_dashboard_service,
)


def test_intelligence_dashboard_displays_all_reports() -> None:
    service = create_intelligence_demo_dashboard_service()
    client = TestClient(create_app(dashboard_service=service))

    page = client.get("/intelligence")
    data = client.get("/api/dashboard").json()

    assert page.status_code == 200
    assert "Trend report" in page.text
    assert "Competitor report" in page.text
    assert "Audience persona" in page.text
    assert "SEO report" in page.text
    assert "Hook analysis" in page.text
    assert "Thumbnail analysis" in page.text
    assert data["intelligence"]["deterministic"] is True
    assert data["niche_discovery"] is not None
    assert data["missions"]
    assert data["workflows"]
    assert data["recent_decisions"]
    assert {employee["job_title"] for employee in data["employees"]} >= {
        "Trend Analyst",
        "Competitor Analyst",
        "Audience Analyst",
        "SEO Director",
        "Retention Engineer",
        "Thumbnail Analyst",
    }


def test_empty_modes_remain_backward_compatible() -> None:
    client = TestClient(create_app())
    assert client.get("/intelligence").status_code == 200
    assert client.get("/api/dashboard").json()["intelligence"] is None


def test_intelligence_demo_factory_is_zero_argument() -> None:
    application = create_intelligence_demo_app()
    assert application.state.dashboard_service.build_snapshot().intelligence
