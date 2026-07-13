from fastapi.testclient import TestClient

from app.main import create_app, create_distribution_demo_app
from distribution.models import PublishingState


def test_distribution_factory_is_zero_argument_and_pages_are_local() -> None:
    client = TestClient(create_distribution_demo_app())

    for path in ("/distribution", "/analytics", "/learning"):
        response = client.get(path)
        assert response.status_code == 200
    assert "Automatic publishing is disabled" in client.get(
        "/distribution"
    ).text
    assert "No ML training or online learning" in client.get("/learning").text


def test_distribution_demo_preserves_context_and_api_fields() -> None:
    client = TestClient(create_distribution_demo_app())
    payload = client.get("/api/dashboard").json()

    assert payload["production"] is not None
    assert payload["intelligence"] is not None
    assert payload["creative_quality"] is not None
    assert payload["distribution"]["publication_status"] == (
        PublishingState.METRICS_IMPORTED.value
    )
    assert payload["analytics"]["metrics"]["views"] == 1000
    assert payload["learning"]["ml_training_performed"] is False
    assert "Distribution Director" in {
        employee["job_title"] for employee in payload["directors"]
    }
    assert len(payload["employees"]) == 40


def test_empty_dashboard_remains_empty_and_backward_compatible() -> None:
    payload = TestClient(create_app()).get("/api/dashboard").json()

    assert payload["distribution"] is None
    assert payload["analytics"] is None
    assert payload["learning"] is None
    assert payload["employees"] == []
