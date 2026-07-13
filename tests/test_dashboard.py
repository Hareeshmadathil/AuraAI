"""Tests for the AuraAI Dashboard Foundation v1."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import create_app
from app.dashboard.models import DashboardMode
from app.dashboard.service import DashboardService
from core.constants import (
    AgentStatus,
    ApprovalStatus,
    DecisionOutcome,
    DecisionType,
    DepartmentName,
    JobStatus,
    MissionStatus,
)
from core.decision import DecisionRecord
from core.mission import MissionRecord
from core.models import AgentIdentity, WorkflowRecord


def test_application_factory_creates_fastapi_app() -> None:
    """Create an isolated FastAPI application without runtime state."""

    application = create_app()

    assert isinstance(application, FastAPI)
    assert application.title == "AuraAI Dashboard"


def test_dashboard_page_returns_html() -> None:
    """Render the local command center without external dependencies."""

    response = TestClient(create_app()).get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "AuraAI Command Center" in response.text
    assert "No missions supplied" in response.text


def test_sidebar_css_preserves_scrollable_desktop_and_mobile_flow() -> None:
    """Keep long desktop navigation accessible without trapping mobile flow."""

    response = TestClient(create_app()).get("/static/css/dashboard.css")

    assert response.status_code == 200
    stylesheet = response.text
    assert "height: 100dvh" in stylesheet
    assert "overflow-y: auto" in stylesheet
    assert "overflow-x: hidden" in stylesheet
    assert "scrollbar-width: thin" in stylesheet
    assert "height: auto; overflow: visible" in stylesheet


def test_health_endpoint_returns_structured_json() -> None:
    """Report the local web layer as operational."""

    response = TestClient(create_app()).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "AuraAI Dashboard",
        "operational": True,
        "test_status": "not_supplied",
    }


def test_dashboard_api_returns_empty_snapshot() -> None:
    """Return safe zero-state data when no runtime is supplied."""

    response = TestClient(create_app()).get("/api/dashboard")
    data = response.json()

    assert response.status_code == 200
    assert data["active_missions"] == 0
    assert data["mode"] == "empty"
    assert data["employees_working"] == 0
    assert data["pending_decisions"] == 0
    assert data["active_workflows"] == 0
    assert data["employees"] == []
    assert data["missions"] == []
    assert data["workflows"] == []
    assert data["recent_decisions"] == []
    assert data["system_health"]["status"] == "healthy"


def test_demo_dashboard_is_visibly_sample_data() -> None:
    """Label both demo HTML and JSON as non-production sample data."""

    client = TestClient(create_app(mode=DashboardMode.DEMO))

    page = client.get("/")
    data = client.get("/api/dashboard").json()

    assert page.status_code == 200
    assert "DEMO DATA" in page.text
    assert data["mode"] == "demo"
    assert data["data_label"] == "DEMO / LOCAL SAMPLE DATA"
    assert len(data["employees"]) == 40
    assert data["executives"]
    assert data["directors"]
    assert data["specialists"]


def test_service_counts_working_employees() -> None:
    """Count only employees in the working state."""

    service = DashboardService(
        employees=[
            AgentIdentity(
                name="Aura",
                job_title="Chief Executive Officer",
                department=DepartmentName.EXECUTIVE,
                status=AgentStatus.WORKING,
            ),
            AgentIdentity(
                name="Atlas",
                job_title="Research Director",
                department=DepartmentName.RESEARCH,
                status=AgentStatus.IDLE,
            ),
        ]
    )

    snapshot = service.build_snapshot()

    assert snapshot.employees_working == 1
    assert snapshot.employees_idle == 1
    assert len(snapshot.employees) == 2


def test_service_counts_active_missions() -> None:
    """Count planning and active missions while excluding drafts."""

    active = MissionRecord(
        title="Active creator mission",
        description="Execute an approved content mission.",
        status=MissionStatus.ACTIVE,
        approval_status=ApprovalStatus.APPROVED,
    )
    draft = MissionRecord(
        title="Draft creator mission",
        description="Await approval before any execution.",
    )

    snapshot = DashboardService(missions=[active, draft]).build_snapshot()

    assert snapshot.active_missions == 1
    assert len(snapshot.missions) == 2


def test_service_counts_pending_decisions() -> None:
    """Count decisions whose outcome remains pending."""

    pending = DecisionRecord(
        title="Choose campaign direction",
        decision_type=DecisionType.STRATEGIC,
    )
    completed = DecisionRecord(
        title="Approve campaign direction",
        decision_type=DecisionType.STRATEGIC,
    )
    completed.decide(
        outcome=DecisionOutcome.APPROVED,
        reasoning="The plan is ready for deterministic execution.",
        confidence_score=0.9,
    )

    snapshot = DashboardService(
        decisions=[pending, completed]
    ).build_snapshot()

    assert snapshot.pending_decisions == 1
    assert len(snapshot.recent_decisions) == 2


def test_service_counts_active_workflows() -> None:
    """Count only running workflow records as active."""

    running = WorkflowRecord(
        name="Active publishing workflow",
        status=JobStatus.RUNNING,
    )
    completed = WorkflowRecord(
        name="Completed research workflow",
        status=JobStatus.COMPLETED,
    )

    snapshot = DashboardService(
        workflows=[running, completed]
    ).build_snapshot()

    assert snapshot.active_workflows == 1
    assert snapshot.workflows[1].progress_percentage == 100.0


def test_dashboard_secondary_pages_return_html() -> None:
    """Render every functional and planned navigation destination."""

    client = TestClient(create_app())

    for path in (
        "/employees",
        "/missions",
        "/workflows",
        "/decisions",
        "/system",
        "/research",
        "/marketing",
    ):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")


def test_dashboard_requires_no_environment_secrets(monkeypatch) -> None:
    """Create and query the dashboard without provider credentials."""

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    client = TestClient(create_app())

    assert client.get("/health").status_code == 200
    assert client.get("/api/dashboard").status_code == 200
