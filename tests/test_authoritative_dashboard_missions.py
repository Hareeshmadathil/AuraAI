"""Phase 1 tests for authoritative normal-dashboard mission reads."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import app.runtime.runtime_dashboard as runtime_dashboard_module
from app.main import create_demo_app, create_runtime_app
from app.runtime.composition import create_runtime_application_services
from core import DepartmentName
from mission_control import MissionControlStatus, MissionRecord
from runtime_engine.event_bus import RuntimeEventBus
from runtime_engine.state_manager import RuntimeStateManager


def create_mission(application) -> MissionRecord:
    control = application.state.mission_control_service
    return control.create_mission(
        MissionRecord(
            title="Authoritative dashboard mission",
            objective="Prove the dashboard reads canonical state.",
            founder_owner="Founder",
            required_departments=[DepartmentName.RESEARCH],
        )
    )


def test_dashboard_reads_shared_mission_control_and_reflects_transitions(
    tmp_path: Path,
) -> None:
    application = create_runtime_app(
        database_path=tmp_path / "mission-control.db",
        allowed_root=tmp_path,
    )
    client = TestClient(application)
    mission = create_mission(application)

    created = client.get("/api/dashboard").json()["missions"][0]
    assert created["mission_id"] == str(mission.mission_id)
    assert created["status"] == MissionControlStatus.CREATED.value

    application.state.mission_control_service.transition(
        mission.mission_id,
        MissionControlStatus.READY,
    )
    transitioned = client.get("/api/dashboard").json()["missions"][0]
    assert transitioned["status"] == MissionControlStatus.READY.value


def test_dashboard_projection_is_read_only(tmp_path: Path) -> None:
    application = create_runtime_app(
        database_path=tmp_path / "mission-control.db",
        allowed_root=tmp_path,
    )
    mission = create_mission(application)
    control = application.state.mission_control_service
    events_before = control.list_events(mission.mission_id)

    TestClient(application).get("/api/dashboard")

    assert control.get_mission(mission.mission_id) == mission
    assert control.list_events(mission.mission_id) == events_before


def test_normal_composition_creates_no_runtime_state_manager_mission_store(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def forbidden_runtime_state(*args, **kwargs):
        raise AssertionError("Normal composition created legacy runtime state.")

    monkeypatch.setattr(
        runtime_dashboard_module,
        "RuntimeStateManager",
        forbidden_runtime_state,
    )
    services = create_runtime_application_services(
        database_path=tmp_path / "mission-control.db",
        allowed_root=tmp_path,
    )

    assert services.dashboard_service.build_snapshot().missions == []


def test_legacy_non_mission_runtime_projection_remains_compatible() -> None:
    state_manager = RuntimeStateManager(RuntimeEventBus())
    service = runtime_dashboard_module.create_runtime_dashboard_service(
        state_manager=state_manager,
    )

    snapshot = service.build_snapshot()
    assert snapshot.employees
    assert snapshot.missions == []
    assert service.mission_control_service is None


def test_demo_factory_remains_isolated_from_mission_control() -> None:
    application = create_demo_app()
    snapshot = TestClient(application).get("/api/dashboard").json()

    assert application.state.mission_control_service is None
    assert application.state.runtime_manager is None
    assert snapshot["mode"] == "demo"
    assert snapshot["missions"]
