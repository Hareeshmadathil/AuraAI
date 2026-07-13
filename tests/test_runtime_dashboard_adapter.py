"""Tests for runtime-to-dashboard snapshot adaptation."""

from uuid import uuid4

from app.dashboard.service import DashboardService
from core import AgentStatus, DepartmentName, JobStatus, MissionStatus
from runtime_engine.dashboard_adapter import create_dashboard_service_from_runtime
from runtime_engine.models import (
    RuntimeEmployeeState,
    RuntimeEvent,
    RuntimeEventType,
    RuntimeHealthComponent,
    RuntimeMissionState,
    RuntimeMode,
    RuntimeSnapshot,
    RuntimeStatistics,
    RuntimeWorkflowState,
)


def test_runtime_snapshot_maps_to_dashboard_service() -> None:
    mission_id, workflow_id = uuid4(), uuid4()
    snapshot = RuntimeSnapshot(
        mode=RuntimeMode.RUNNING,
        statistics=RuntimeStatistics(
            registered_missions=1,
            active_missions=1,
            completed_missions=0,
            failed_missions=0,
            registered_workflows=1,
            active_workflows=1,
            employees_working=1,
            employees_idle=0,
            pending_decisions=0,
            total_events=1,
        ),
        employees=[
            RuntimeEmployeeState(
                agent_id=uuid4(),
                name="Runtime Worker",
                job_title="Research Specialist",
                department=DepartmentName.RESEARCH,
                status=AgentStatus.WORKING,
            )
        ],
        missions=[
            RuntimeMissionState(
                mission_id=mission_id,
                title="Runtime mission",
                status=MissionStatus.ACTIVE,
                progress_percentage=40,
            )
        ],
        workflows=[
            RuntimeWorkflowState(
                workflow_id=workflow_id,
                mission_id=mission_id,
                name="Runtime workflow",
                status=JobStatus.RUNNING,
                progress_percentage=60,
            )
        ],
        recent_events=[
            RuntimeEvent(
                event_type=RuntimeEventType.WORKFLOW_STARTED,
                message="Workflow started.",
                workflow_id=workflow_id,
            )
        ],
        system_health={
            "runtime": RuntimeHealthComponent(status="operational")
        },
    )

    dashboard = create_dashboard_service_from_runtime(snapshot).build_snapshot()

    assert dashboard.mode.value == "injected"
    assert dashboard.employees_working == 1
    assert dashboard.active_missions == 1
    assert dashboard.active_workflows == 1
    assert dashboard.workflows[0].progress_percentage == 60
    assert dashboard.activity[0].detail == "Workflow started."
    assert dashboard.system_health.status.value == "healthy"


def test_existing_empty_dashboard_remains_unchanged() -> None:
    snapshot = DashboardService().build_snapshot()
    assert snapshot.mode.value == "empty"
    assert snapshot.employees == []
    assert snapshot.active_missions == 0
