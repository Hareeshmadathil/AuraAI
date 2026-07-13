"""Production dashboard integration and compatibility tests."""

from fastapi.testclient import TestClient

from app.dashboard.service import DashboardService
from app.main import create_app, create_content_production_demo_app


def test_production_page_returns_truthful_sample_summary() -> None:
    client = TestClient(create_content_production_demo_app())
    response = client.get("/production")
    assert response.status_code == 200
    assert "SAMPLE" in response.text
    assert "PLANNED" in response.text
    assert "NOT RENDERED" in response.text
    assert "Hybrid" in response.text
    assert "Storyboard scenes" in response.text
    assert "Founder Approval" in response.text


def test_production_api_contains_additive_structured_summary() -> None:
    client = TestClient(create_content_production_demo_app())
    data = client.get("/api/dashboard").json()
    production = data["production"]
    assert production["script_word_count"] > 0
    assert production["storyboard_scene_count"] == 7
    assert production["visual_request_count"] == 7
    assert production["quality_score"] > 90
    assert production["assembly_status"] == "not_rendered"
    assert production["media_rendered"] is False
    assert data["niche_discovery"] is not None
    assert data["intelligence"] is not None
    assert data["missions"]
    assert data["workflows"]
    assert data["recent_decisions"]
    assert {employee["job_title"] for employee in data["employees"]} >= {
        "Production Director",
        "Script Writer",
        "Storyboard Artist",
        "Voice Artist",
        "Thumbnail Designer",
        "Shorts Editor",
        "Video Editor",
        "Production Quality Controller",
    }


def test_existing_empty_mode_and_routes_remain_unaffected() -> None:
    snapshot = DashboardService().build_snapshot()
    assert snapshot.production is None
    client = TestClient(create_app())
    assert client.get("/").status_code == 200
    assert client.get("/api/dashboard").json()["production"] is None
    empty_page = client.get("/production")
    assert empty_page.status_code == 200
    assert "No production package supplied" in empty_page.text
