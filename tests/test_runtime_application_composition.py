"""Phase 1 tests for the normal application composition lifecycle."""

from __future__ import annotations

import importlib
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as application_module
import app.runtime.composition as composition_module
from app.main import create_app, create_runtime_app
from mission_control.repository import SQLiteMissionControlRepository


def test_composition_creates_one_shared_persistent_authority(
    monkeypatch,
    tmp_path: Path,
) -> None:
    created_repositories: list[SQLiteMissionControlRepository] = []
    repository_type = composition_module.SQLiteMissionControlRepository

    def create_repository(*args, **kwargs):
        repository = repository_type(*args, **kwargs)
        created_repositories.append(repository)
        return repository

    monkeypatch.setattr(
        composition_module,
        "SQLiteMissionControlRepository",
        create_repository,
    )
    services = composition_module.create_runtime_application_services(
        database_path=tmp_path / "mission-control.db",
        allowed_root=tmp_path,
    )

    assert len(created_repositories) == 1
    assert services.mission_control_service.repository is created_repositories[0]
    assert (
        services.runtime_manager.mission_control
        is services.mission_control_service
    )
    assert (
        services.dashboard_service.mission_control_service
        is services.mission_control_service
    )


def test_runtime_app_injects_same_service_into_every_surface(
    tmp_path: Path,
) -> None:
    application = create_runtime_app(
        database_path=tmp_path / "mission-control.db",
        allowed_root=tmp_path,
    )
    services = application.state.runtime_services

    assert application.state.mission_control_service is services.mission_control_service
    assert application.state.runtime_manager is services.runtime_manager
    assert (
        application.state.dashboard_service.mission_control_service
        is services.mission_control_service
    )
    response = TestClient(application).get("/api/mission-control")
    assert response.status_code == 200


def test_repeated_module_import_does_not_initialize_application(
    monkeypatch,
) -> None:
    calls = 0

    def forbidden_startup():
        nonlocal calls
        calls += 1
        raise AssertionError("Import attempted normal application startup.")

    monkeypatch.setattr(
        composition_module,
        "create_runtime_application_services",
        forbidden_startup,
    )
    reloaded = importlib.reload(application_module)
    reloaded_again = importlib.reload(reloaded)

    assert calls == 0
    assert reloaded_again.app.is_initialized is False


def test_create_app_public_api_still_builds_an_empty_app() -> None:
    application = create_app()

    assert TestClient(application).get("/api/dashboard").status_code == 200
    assert application.state.mission_control_service is None
    assert application.state.runtime_manager is None
