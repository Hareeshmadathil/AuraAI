"""Narrow conversion from runtime projections to dashboard inputs."""

from __future__ import annotations

from app.dashboard.models import (
    ActivityEventSummary,
    ActivityEventType,
    DashboardMode,
    EmployeeGroup,
    EmployeeStatusSummary,
    MissionStatusSummary,
    SystemHealthStatus,
    SystemHealthSummary,
    WorkflowStatusSummary,
)
from app.dashboard.service import DashboardService
from runtime_engine.models import RuntimeEventSeverity, RuntimeSnapshot
from production.models import ProductionPackage


def create_dashboard_service_from_runtime(
    runtime_snapshot: RuntimeSnapshot,
    *,
    mode: DashboardMode = DashboardMode.INJECTED,
    data_label: str = "INJECTED RUNTIME STATE",
    production_package: ProductionPackage | None = None,
) -> DashboardService:
    """Create an injected dashboard service from one runtime snapshot."""

    employees = [
        EmployeeStatusSummary(
            agent_id=employee.agent_id,
            name=employee.name,
            job_title=employee.job_title,
            department=employee.department,
            status=employee.status,
            enabled=True,
            group=_employee_group(employee.department.value, employee.job_title),
        )
        for employee in runtime_snapshot.employees
    ]
    missions = [
        MissionStatusSummary(
            mission_id=mission.mission_id,
            title=mission.title,
            status=mission.status,
            priority="normal",
            progress_percentage=mission.progress_percentage,
        )
        for mission in runtime_snapshot.missions
    ]
    workflows = [
        WorkflowStatusSummary(
            workflow_id=workflow.workflow_id,
            name=workflow.name,
            status=workflow.status,
            progress_percentage=workflow.progress_percentage,
            task_count=0,
        )
        for workflow in runtime_snapshot.workflows
    ]
    activity = [
        ActivityEventSummary(
            event_id=str(event.event_id),
            event_type=_activity_type(event.event_type.value),
            title=event.event_type.value.replace("_", " ").title(),
            detail=event.message,
            occurred_at=event.timestamp,
        )
        for event in reversed(runtime_snapshot.recent_events)
    ]
    health = _map_health(runtime_snapshot)
    return DashboardService(
        mode=mode,
        data_label=data_label,
        employees=employees,
        missions=missions,
        decisions=runtime_snapshot.decisions,
        workflows=workflows,
        activity=activity,
        system_health=health,
        production_package=production_package,
    )


def _employee_group(department: str, job_title: str) -> EmployeeGroup:
    if department == "executive":
        return EmployeeGroup.EXECUTIVE
    if job_title.endswith("Director"):
        return EmployeeGroup.DIRECTOR
    return EmployeeGroup.SPECIALIST


def _activity_type(event_type: str) -> ActivityEventType:
    prefix = event_type.split("_", maxsplit=1)[0]
    return {
        "mission": ActivityEventType.MISSION,
        "workflow": ActivityEventType.WORKFLOW,
        "task": ActivityEventType.WORKFLOW,
        "employee": ActivityEventType.EMPLOYEE,
        "decision": ActivityEventType.DECISION,
    }.get(prefix, ActivityEventType.SYSTEM)


def _map_health(snapshot: RuntimeSnapshot) -> SystemHealthSummary:
    degraded = any(
        component.status.lower() not in {"healthy", "operational"}
        for component in snapshot.system_health.values()
    )
    errors = any(
        event.severity == RuntimeEventSeverity.ERROR
        for event in snapshot.recent_events
    )
    status = (
        SystemHealthStatus.DEGRADED
        if degraded or errors
        else SystemHealthStatus.HEALTHY
    )
    return SystemHealthSummary(
        status=status,
        web_service_operational=True,
        test_status="runtime_snapshot",
        message="Runtime engine snapshot is connected.",
    )
