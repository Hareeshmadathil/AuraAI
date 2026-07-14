"""Deterministic, non-persistent sample state for the local dashboard."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import Field

from app.dashboard.models import (
    DashboardMode,
    SystemHealthStatus,
    SystemHealthSummary,
)
from app.dashboard.service import DashboardService
from app.runtime.company_roster import create_company_roster
from core.constants import (
    AgentStatus,
    DecisionType,
    DepartmentName,
    JobStatus,
    TaskPriority,
)
from core.decision import DecisionRecord
from core.models import AuraBaseModel, WorkflowRecord
from mission_engine import (
    ArtifactRegistry,
    InMemoryMissionRepository,
    Mission,
    MissionArtifactType,
    MissionCapability,
    MissionExecutionStatus,
    MissionManager,
)


class DashboardWorkflowState(AuraBaseModel):
    """Workflow record paired with exact runtime progress."""

    record: WorkflowRecord
    progress_percentage: float = Field(ge=0.0, le=100.0)


def create_demo_dashboard_service() -> DashboardService:
    """Create explicit local sample data for dashboard exploration."""

    roster = create_company_roster()
    working_titles = {
        "Chief Executive Officer",
        "Chief Operating Officer",
        "Research Director",
        "Trend Hunter",
    }

    for employee in roster.employees:
        status = (
            AgentStatus.WORKING
            if employee.job_title in working_titles
            else AgentStatus.IDLE
        )
        employee.set_status(status)

    mission = _create_demo_mission(roster.employees)
    decision = _create_demo_decision(roster.executives[0].agent_id)
    workflow = _create_demo_workflow()

    return DashboardService(
        mode=DashboardMode.DEMO,
        data_label="DEMO / LOCAL SAMPLE DATA",
        employees=roster.employees,
        missions=(mission,),
        decisions=(decision,),
        workflows=(workflow,),
        system_health=SystemHealthSummary(
            status=SystemHealthStatus.HEALTHY,
            web_service_operational=True,
            test_status="sample_not_live",
            message=(
                "Operational local demonstration. Values shown are "
                "sample data and are not production activity."
            ),
        ),
    )


def _create_demo_mission(employees) -> Mission:
    """Create one V1 mission with assignments and artifact metadata."""

    manager = MissionManager(
        InMemoryMissionRepository(),
        ArtifactRegistry(),
    )
    mission = manager.create_mission(
        title="Launch the AuraAI educational content pilot",
        objective=(
            "Plan a safe, evidence-based local content campaign across "
            "the currently supported platforms."
        ),
        capability=MissionCapability.CONTENT_PIPELINE,
        priority=TaskPriority.HIGH,
        assigned_departments=[
            DepartmentName.RESEARCH,
            DepartmentName.MARKETING,
        ],
    )
    selected = {
        employee.job_title: employee
        for employee in employees
        if employee.job_title in {"Research Director", "Trend Hunter"}
    }
    for employee in selected.values():
        mission = manager.assign_employee(
            mission.mission_id,
            employee_id=employee.agent_id,
            employee_name=employee.name,
            department=employee.department,
        )
    for state in (
        MissionExecutionStatus.PLANNING,
        MissionExecutionStatus.RESEARCH,
    ):
        mission = manager.update_mission_state(mission.mission_id, state)
    manager.register_artifact(
        mission.mission_id,
        artifact_type=MissionArtifactType.RESEARCH,
        name="Educational pilot research brief",
        summary="Deterministic sample research metadata.",
    )
    manager.register_artifact(
        mission.mission_id,
        artifact_type=MissionArtifactType.KEYWORDS,
        name="Pilot keyword plan",
        summary="Deterministic sample keyword metadata.",
    )
    return manager.update_mission_state(
        mission.mission_id,
        MissionExecutionStatus.SEO,
    )


def _create_demo_decision(executive_agent_id: UUID) -> DecisionRecord:
    """Create one pending executive decision for sample governance."""

    decision = DecisionRecord(
        title="Review the educational pilot launch package",
        decision_type=DecisionType.STRATEGIC,
        decision_maker_agent_id=executive_agent_id,
        decision_maker_name="Aura",
        department=DepartmentName.EXECUTIVE,
        requires_user_confirmation=True,
        created_at=datetime(2026, 7, 12, 10, 0, tzinfo=UTC),
    )
    decision.add_evidence(
        title="Local sample plan",
        description=(
            "A deterministic plan is available for dashboard review."
        ),
        source_type="demo_state",
        reliability_score=1.0,
    )
    decision.updated_at = datetime(2026, 7, 12, 10, 45, tzinfo=UTC)
    return decision


def _create_demo_workflow() -> DashboardWorkflowState:
    """Create one running sample workflow with exact progress."""

    record = WorkflowRecord(
        name="Educational pilot launch workflow",
        description="Coordinate research, marketing, and review steps.",
        status=JobStatus.RUNNING,
        created_at=datetime(2026, 7, 12, 9, 30, tzinfo=UTC),
    )
    record.add_task(
        uuid5(NAMESPACE_URL, "https://auraai.local/demo/research-step")
    )
    record.add_task(
        uuid5(NAMESPACE_URL, "https://auraai.local/demo/marketing-step")
    )
    record.updated_at = datetime(2026, 7, 12, 11, 0, tzinfo=UTC)
    return DashboardWorkflowState(
        record=record,
        progress_percentage=50.0,
    )
