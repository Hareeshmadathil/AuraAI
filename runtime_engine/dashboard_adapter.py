"""Narrow conversion from runtime projections to dashboard inputs."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from app.dashboard.models import (
    ActivityEventSummary,
    ActivityEventType,
    DashboardMode,
    EmployeeStatusSummary,
    MissionStatusSummary,
    SystemHealthStatus,
    SystemHealthSummary,
    WorkflowStatusSummary,
    classify_employee_group,
)
from app.dashboard.service import DashboardService
from runtime_engine.models import RuntimeEventSeverity, RuntimeSnapshot
from production.models import ProductionPackage
from intelligence.models import IntelligencePackage
from core.models import AgentIdentity
from production.rendering.models import LocalRenderResult
from creative_quality.models import CreativeQualityPackage


class EmployeeIdentityProvider(Protocol):
    """Structural type for employee objects exposing an identity model."""

    identity: AgentIdentity


def create_dashboard_service_from_runtime(
    runtime_snapshot: RuntimeSnapshot,
    *,
    mode: DashboardMode = DashboardMode.INJECTED,
    data_label: str = "INJECTED RUNTIME STATE",
    production_package: ProductionPackage | None = None,
    intelligence_package: IntelligencePackage | None = None,
    local_render_result: LocalRenderResult | None = None,
    company_roster: Iterable[AgentIdentity | EmployeeIdentityProvider] = (),
    niche_discovery: dict[str, Any] | None = None,
    creative_quality_package: CreativeQualityPackage | None = None,
) -> DashboardService:
    """Create an injected dashboard service from one runtime snapshot."""

    employees = _merge_employees(runtime_snapshot, company_roster)
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
    activity = build_activity_summaries(runtime_snapshot)
    health = build_system_health_summary(runtime_snapshot)
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
        intelligence_package=intelligence_package,
        local_render_result=local_render_result,
        niche_discovery=niche_discovery,
        creative_quality_package=creative_quality_package,
    )


def build_activity_summaries(
    runtime_snapshot: RuntimeSnapshot,
) -> list[ActivityEventSummary]:
    """Convert runtime events into dashboard-safe activity entries."""

    return [
        ActivityEventSummary(
            event_id=str(event.event_id),
            event_type=_activity_type(event.event_type.value),
            title=event.event_type.value.replace("_", " ").title(),
            detail=event.message,
            occurred_at=event.timestamp,
        )
        for event in reversed(runtime_snapshot.recent_events)
    ]


def _merge_employees(
    snapshot: RuntimeSnapshot,
    company_roster: Iterable[AgentIdentity | EmployeeIdentityProvider],
) -> list[EmployeeStatusSummary]:
    """Overlay runtime statuses onto a complete injected company roster."""

    runtime_by_title = {
        employee.job_title: employee for employee in snapshot.employees
    }
    values: list[EmployeeStatusSummary] = []
    seen_titles: set[str] = set()
    for employee in company_roster:
        identity = AgentIdentity.model_validate(
            getattr(employee, "identity", employee)
        )
        runtime = runtime_by_title.get(identity.job_title)
        values.append(
            EmployeeStatusSummary(
                agent_id=identity.agent_id,
                name=identity.name,
                job_title=identity.job_title,
                department=identity.department,
                status=runtime.status if runtime else identity.status,
                enabled=identity.enabled,
                group=classify_employee_group(
                    identity.department, identity.job_title
                ),
            )
        )
        seen_titles.add(identity.job_title)
    values.extend(
        EmployeeStatusSummary(
            agent_id=employee.agent_id,
            name=employee.name,
            job_title=employee.job_title,
            department=employee.department,
            status=employee.status,
            enabled=True,
            group=classify_employee_group(
                employee.department, employee.job_title
            ),
        )
        for employee in snapshot.employees
        if employee.job_title not in seen_titles
    )
    return values


def _activity_type(event_type: str) -> ActivityEventType:
    prefix = event_type.split("_", maxsplit=1)[0]
    return {
        "mission": ActivityEventType.MISSION,
        "workflow": ActivityEventType.WORKFLOW,
        "task": ActivityEventType.WORKFLOW,
        "employee": ActivityEventType.EMPLOYEE,
        "decision": ActivityEventType.DECISION,
    }.get(prefix, ActivityEventType.SYSTEM)


def build_system_health_summary(snapshot: RuntimeSnapshot) -> SystemHealthSummary:
    """Map runtime component health and errors to dashboard health."""
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
