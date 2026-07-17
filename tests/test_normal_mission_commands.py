"""Final Phase 1 tests for normal mission command authority."""

from __future__ import annotations

import inspect
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app, create_demo_app, create_runtime_app
from app.runtime.mission_commands import MissionCommandService
from agents.base_employee import BaseEmployee
from core import DepartmentName, OperationResult, TaskRecord as EmployeeTask
from mission_control import MissionControlStatus, TaskRecord, TaskStatus
from runtime_engine.orchestrator import RuntimeOrchestrator


class CommandBoundaryEmployee(BaseEmployee):
    """Employee with a generic deterministic command contract."""

    def __init__(self) -> None:
        super().__init__(
            name="Command Boundary Worker",
            job_title="Command Boundary Worker",
            department=DepartmentName.RESEARCH,
        )

    def perform_task(self, task: EmployeeTask) -> OperationResult:
        return OperationResult.ok(
            "Command boundary task completed.",
            data={"input_marker": task.input_data["marker"]},
        )


def mission_payload(title: str = "Normal application mission") -> dict[str, str]:
    return {
        "title": title,
        "objective": "Verify the authoritative normal command boundary.",
        "founder_owner": "Founder",
    }


def build_application(tmp_path: Path):
    application = create_runtime_app(
        database_path=tmp_path / "mission-control.db",
        allowed_root=tmp_path,
    )
    return application, TestClient(application)


def submit(client: TestClient) -> dict:
    response = client.post("/api/missions", json=mission_payload())
    assert response.status_code == 201
    return response.json()


def test_submission_uses_shared_mission_control_and_dashboard(
    tmp_path: Path,
) -> None:
    application, client = build_application(tmp_path)
    submitted = submit(client)
    mission_id = submitted["mission_id"]
    services = application.state.runtime_services

    assert services.mission_command_service.runtime_manager is services.runtime_manager
    assert services.runtime_manager.mission_control is services.mission_control_service
    assert str(services.mission_control_service.list_missions()[0].mission_id) == mission_id
    assert client.get("/api/dashboard").json()["missions"][0]["mission_id"] == mission_id
    assert client.get("/api/mission-control").json()["missions"][0]["mission_id"] == mission_id


def test_run_next_uses_shared_manager_and_employee_dispatcher(
    monkeypatch,
    tmp_path: Path,
) -> None:
    application, client = build_application(tmp_path)
    mission_id = submit(client)["mission_id"]
    services = application.state.runtime_services
    employee = CommandBoundaryEmployee()
    services.employee_registry.register(employee)
    control = services.mission_control_service
    mission_uuid = control.list_missions()[0].mission_id
    task = control.add_task(
        TaskRecord(
            mission_id=mission_uuid,
            title="Research authoritative boundary",
            department=DepartmentName.RESEARCH,
            assigned_agent_id=employee.agent_id,
            idempotency_key=f"{mission_id}:research",
            payload={"marker": "shared-dispatcher"},
        )
    )
    control.transition(mission_uuid, MissionControlStatus.READY)
    control.transition(mission_uuid, MissionControlStatus.RUNNING)
    manager_calls = 0
    dispatcher_calls = 0
    manager_run_next = services.runtime_manager.run_next
    dispatcher_dispatch = services.employee_dispatcher.dispatch

    def tracked_run_next(selected_mission_id):
        nonlocal manager_calls
        manager_calls += 1
        return manager_run_next(selected_mission_id)

    def tracked_dispatch(command):
        nonlocal dispatcher_calls
        dispatcher_calls += 1
        return dispatcher_dispatch(command)

    monkeypatch.setattr(services.runtime_manager, "run_next", tracked_run_next)
    monkeypatch.setattr(services.employee_dispatcher, "dispatch", tracked_dispatch)
    response = client.post(f"/api/missions/{mission_id}/run-next")

    assert response.status_code == 200
    assert response.json()["task"]["task_id"] == str(task.task_id)
    assert manager_calls == 1
    assert dispatcher_calls == 1
    assert control.list_tasks(mission_uuid)[0].status == TaskStatus.COMPLETED


def test_normal_commands_never_invoke_legacy_orchestrator(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("Legacy orchestrator executed a normal command.")

    monkeypatch.setattr(RuntimeOrchestrator, "start_mission", forbidden)
    monkeypatch.setattr(RuntimeOrchestrator, "run_mission", forbidden)
    monkeypatch.setattr(RuntimeOrchestrator, "run_next_mission_step", forbidden)
    _, client = build_application(tmp_path)

    assert client.post("/api/missions", json=mission_payload()).status_code == 201


def test_command_adapter_has_no_repository_or_employee_bypass() -> None:
    source = inspect.getsource(MissionCommandService)

    assert ".repository" not in source
    assert "accept_task" not in source
    assert "execute_current_task" not in source
    assert "RuntimeOrchestrator" not in source


def test_unscheduled_and_ineligible_work_cannot_execute(tmp_path: Path) -> None:
    application, client = build_application(tmp_path)
    mission_id = submit(client)["mission_id"]
    control = application.state.mission_control_service
    mission_uuid = control.list_missions()[0].mission_id
    task = control.add_task(
        TaskRecord(
            mission_id=mission_uuid,
            title="Must remain unscheduled",
            department=DepartmentName.RESEARCH,
            idempotency_key=f"{mission_id}:blocked",
        )
    )

    response = client.post(f"/api/missions/{mission_id}/run-next")

    assert response.status_code == 409
    assert control.list_tasks(mission_uuid)[0].task_id == task.task_id
    assert control.list_tasks(mission_uuid)[0].status == TaskStatus.PENDING


def test_non_runtime_and_demo_apps_expose_no_mission_commands() -> None:
    empty = create_app()
    demo = create_demo_app()

    assert TestClient(empty).post("/api/missions", json=mission_payload()).status_code == 503
    assert TestClient(demo).post("/api/missions", json=mission_payload()).status_code == 503
    assert empty.state.mission_command_service is None
    assert demo.state.mission_command_service is None
