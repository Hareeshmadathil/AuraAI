"""End-to-end offline Mission Zero integration tests."""
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from company_missions.mission_zero_integration import MissionZeroIntegration
from mission_control import (
    ApprovalState,
    MissionControlService,
    MissionControlStatus,
    SQLiteMissionControlRepository,
    TaskStatus,
)


EXPECTED_TIMELINE = (
    "Mission Created",
    "CEO Review Complete",
    "COO Coordination Complete",
    "Trend Hunter Complete",
    "Intelligence Director Complete",
    "Knowledge Manager Complete",
    "Web Intelligence Offline Complete",
    "Research Department Complete",
    "Production Research Complete",
    "Provider Router Offline Complete",
    "Script Package Complete",
    "Production Connector Complete",
    "Private Video Production Package Complete",
    "Creative Quality Complete",
    "Waiting For Founder Approval",
)


def run_mission(tmp_path: Path):
    repository = SQLiteMissionControlRepository(
        tmp_path / "mission-control.db",
        allowed_root=tmp_path,
    )
    control = MissionControlService(repository)
    result = MissionZeroIntegration(
        control,
        project_root=Path(__file__).resolve().parents[1],
    ).run()
    return result, control, repository


def test_complete_offline_mission_reaches_founder_approval(tmp_path):
    result, _, repository = run_mission(tmp_path)

    assert result.timeline == EXPECTED_TIMELINE
    assert result.projection.missions[0].status == MissionControlStatus.APPROVAL_REQUIRED
    assert len(repository.list_tasks()) == 14
    assert sum(task.status == TaskStatus.COMPLETED for task in repository.list_tasks()) == 13
    assert repository.list_tasks()[-1].status == TaskStatus.APPROVAL_REQUIRED
    assert len(result.projection.artifacts) == 13
    assert result.approval_request.state == ApprovalState.PENDING
    assert result.approval_request.requested_action == "approve_mission_zero_content"


def test_every_result_is_correlated_and_replayable(tmp_path):
    result, control, repository = run_mission(tmp_path)
    mission_id = result.projection.missions[0].mission_id
    task_ids = {task.task_id for task in repository.list_tasks(mission_id)}

    assert all(artifact.task_id in task_ids for artifact in repository.list_artifacts(mission_id))
    assert all(artifact.provenance["offline"] is True for artifact in repository.list_artifacts(mission_id))
    events = control.replay(mission_id)
    assert [event.sequence for event in events] == sorted(event.sequence for event in events)
    assert events[-1].event_type == "mission.transitioned"
    assert not any(event.event_type in {"render.started", "upload.started", "publish.started"} for event in events)


def test_existing_dashboard_projects_real_mission_control_state(tmp_path):
    result, control, _ = run_mission(tmp_path)
    app = create_app(
        dashboard_service=result.dashboard_service,
        mission_control_service=control,
    )
    client = TestClient(app)

    mission_control = client.get("/api/mission-control")
    dashboard = client.get("/api/dashboard")
    assert mission_control.status_code == 200
    assert dashboard.status_code == 200
    canonical_id = mission_control.json()["missions"][0]["mission_id"]
    assert dashboard.json()["missions"][0]["mission_id"] == canonical_id
    assert mission_control.json()["pending_approvals"][0]["state"] == "pending"


def test_pipeline_does_not_invoke_external_provider_or_web_execution(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        raise AssertionError("External execution was attempted.")

    monkeypatch.setattr("providers.gemini.transport.UnavailableGeminiTransport.send", forbidden)
    monkeypatch.setattr("web_intelligence.service.WebIntelligenceService.execute", forbidden)
    result, _, _ = run_mission(tmp_path)
    assert result.timeline[-1] == "Waiting For Founder Approval"


def test_protected_founder_input_remains_outside_integration():
    source = Path(__file__).resolve().parents[1] / "company_missions" / "mission_zero_integration.py"
    assert "founder_inputs/mission_zero.json" not in source.read_text(encoding="utf-8")
