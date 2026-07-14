"""Mission Execution Engine V1 dashboard integration tests."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.dashboard.service import DashboardService
from app.main import create_app, create_demo_app
from core.constants import DepartmentName
from mission_engine import (
    ArtifactRegistry,
    InMemoryMissionRepository,
    MissionArtifactType,
    MissionCapability,
    MissionExecutionStatus,
    MissionManager,
)


def build_dashboard_mission():
    """Build a mission with one employee and artifact for projection tests."""

    manager = MissionManager(InMemoryMissionRepository(), ArtifactRegistry())
    mission = manager.create_mission(
        title="Dashboard-backed mission",
        objective="Expose typed execution state without demo-only fields.",
        capability=MissionCapability.CONTENT_PIPELINE,
    )
    employee_id = uuid4()
    mission = manager.assign_employee(
        mission.mission_id,
        employee_id=employee_id,
        employee_name="Atlas",
        department=DepartmentName.RESEARCH,
    )
    manager.register_artifact(
        mission.mission_id,
        artifact_type=MissionArtifactType.RESEARCH,
        name="Research artifact",
        summary="Metadata-only dashboard artifact.",
        produced_by_employee_id=employee_id,
    )
    mission = manager.update_mission_state(
        mission.mission_id,
        MissionExecutionStatus.PLANNING,
    )
    return manager.update_mission_state(
        mission.mission_id,
        MissionExecutionStatus.RESEARCH,
    )


def test_dashboard_snapshot_projects_v1_mission_details() -> None:
    """Expose ID, state, progress, assignees, and artifacts in typed JSON."""

    mission = build_dashboard_mission()
    snapshot = DashboardService(missions=[mission]).build_snapshot()
    summary = snapshot.missions[0]

    assert snapshot.active_missions == 1
    assert summary.mission_id == mission.mission_id
    assert summary.status == MissionExecutionStatus.RESEARCH
    assert summary.progress_percentage == 30.0
    assert summary.assigned_employees == ["Atlas"]
    assert summary.generated_artifacts[0].name == "Research artifact"
    assert summary.capability == "content_pipeline"


def test_mission_page_renders_execution_backbone_fields() -> None:
    """Show the complete mission summary without changing route behavior."""

    mission = build_dashboard_mission()
    client = TestClient(create_app(DashboardService(missions=[mission])))
    response = client.get("/missions")

    assert response.status_code == 200
    assert str(mission.mission_id) in response.text
    assert "Dashboard-backed mission" in response.text
    assert "Research" in response.text
    assert "30.0% complete" in response.text
    assert "Atlas" in response.text
    assert "Research artifact" in response.text


def test_demo_dashboard_uses_v1_mission_objects() -> None:
    """Replace generic demo mission data with a real execution mission."""

    client = TestClient(create_demo_app())
    data = client.get("/api/dashboard").json()
    page = client.get("/missions")
    mission = data["missions"][0]

    assert mission["status"] == "seo"
    assert mission["progress_percentage"] == 50.0
    assert len(mission["assigned_employees"]) == 2
    assert len(mission["generated_artifacts"]) == 2
    assert "Assigned employees" in page.text
    assert "Generated artifacts" in page.text
