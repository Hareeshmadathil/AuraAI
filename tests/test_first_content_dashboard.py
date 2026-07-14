"""Dashboard integration tests for the first mission."""

import inspect

from fastapi.testclient import TestClient

from app.main import create_app, create_first_content_mission_demo_app


def test_factory_is_zero_argument_and_page_is_safe() -> None:
    assert not inspect.signature(create_first_content_mission_demo_app).parameters
    client = TestClient(create_first_content_mission_demo_app())
    response = client.get("/first-content-mission")
    assert response.status_code == 200
    for text in ("FOUNDER REVIEW REQUIRED", "NOT RENDERED", "NOT PUBLISHED", "Creative Quality"):
        assert text in response.text
    lowered = response.text.lower()
    assert "api_key" not in lowered and "raw_response" not in lowered
    snapshot = client.get("/api/dashboard").json()
    assert snapshot["first_content_mission"]["mission_summary"]["current_state"] == "founder_review"
    assert "production_package" not in snapshot["first_content_mission"]
    assert snapshot["workflows"] and snapshot["recent_decisions"]


def test_empty_dashboard_remains_empty() -> None:
    snapshot = TestClient(create_app()).get("/api/dashboard").json()
    assert snapshot["first_content_mission"] is None
