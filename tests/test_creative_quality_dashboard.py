import inspect

from fastapi.testclient import TestClient

from app.main import create_app, create_creative_quality_demo_app


def test_creative_quality_dashboard_displays_scores_gate_and_roster() -> None:
    client = TestClient(create_creative_quality_demo_app())
    response = client.get("/creative-quality")
    data = client.get("/api/dashboard").json()
    assert response.status_code == 200
    assert "Creative Quality Command Center" in response.text
    assert "Internal deterministic heuristic" in response.text
    assert "Founder Review Separate" in response.text
    assert data["creative_quality"]["scores"]["overall"] > 0
    assert data["creative_quality"]["gate"]["status"] == "passed"
    assert len(data["employees"]) == 40
    assert {item["job_title"] for item in data["employees"]} >= {
        "Creative Quality Director",
        "Hook Architect",
        "Factuality Reviewer",
    }
    assert data["intelligence"] is not None
    assert data["production"] is not None


def test_empty_mode_and_zero_argument_factory_are_preserved() -> None:
    client = TestClient(create_app())
    assert client.get("/creative-quality").status_code == 200
    assert client.get("/api/dashboard").json()["creative_quality"] is None
    required = [
        value
        for value in inspect.signature(
            create_creative_quality_demo_app
        ).parameters.values()
        if value.default is inspect.Parameter.empty
    ]
    assert required == []
