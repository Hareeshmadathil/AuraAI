"""Cumulative dashboard and zero-argument factory tests."""

import inspect

from fastapi.testclient import TestClient

from app.main import create_real_content_pilot_demo_app


def test_pilot_factory_is_zero_argument_and_page_is_safe() -> None:
    assert not inspect.signature(create_real_content_pilot_demo_app).parameters
    client = TestClient(create_real_content_pilot_demo_app())

    response = client.get("/mission-pilot")
    assert response.status_code == 200
    assert "FOUNDER REVIEW REQUIRED" in response.text
    assert "NOT RENDERED" in response.text
    assert "NOT PUBLISHED" in response.text
    assert "Aura" in response.text
    assert "Quill" in response.text

    snapshot = client.get("/api/dashboard").json()
    assert snapshot["real_content_pilot"]["mission"]["status"] == "founder_review"
    assert snapshot["production"] is not None
    assert snapshot["creative_quality"] is not None
    assert "api_key" not in response.text
