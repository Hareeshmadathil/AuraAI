"""Normal, demo, and explicit-empty dashboard startup behavior."""
from fastapi.testclient import TestClient

from app.dashboard.models import DashboardMode
from app.main import app, create_app, create_demo_app, create_runtime_app


def _snapshot(application):
    return TestClient(application).get("/api/dashboard").json()


def test_module_app_contains_real_company_roster_without_sample_work():
    snapshot = _snapshot(app)
    assert snapshot["mode"] == "injected"
    assert snapshot["data_label"] == "LOCAL RUNTIME STATE"
    assert snapshot["employees"]
    assert snapshot["missions"] == []
    assert snapshot["workflows"] == []
    assert snapshot["recent_decisions"] == []
    assert snapshot["employees_working"] == 0
    assert snapshot["employees_idle"] == len(snapshot["employees"])


def test_runtime_factory_represents_every_organizational_level():
    snapshot = _snapshot(create_runtime_app())
    assert snapshot["executives"]
    assert snapshot["directors"]
    assert snapshot["specialists"]
    assert len(snapshot["employees"]) == (
        len(snapshot["executives"])
        + len(snapshot["directors"])
        + len(snapshot["specialists"])
    )


def test_demo_factory_remains_sample_data():
    snapshot = _snapshot(create_demo_app())
    assert snapshot["mode"] == "demo"
    assert snapshot["missions"]
    assert snapshot["workflows"]
    assert snapshot["recent_decisions"]
    assert snapshot["employees_working"] > 0


def test_explicit_empty_mode_remains_empty():
    snapshot = _snapshot(create_app(mode=DashboardMode.EMPTY))
    assert snapshot["mode"] == "empty"
    assert snapshot["employees"] == []
    assert snapshot["missions"] == []
    assert snapshot["workflows"] == []
