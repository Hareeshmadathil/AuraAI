"""Tests for the explicit AuraAI dashboard runtime factories."""

from app.dashboard.models import EmployeeGroup
from app.runtime.company_roster import create_company_roster
from app.runtime.demo_state import create_demo_dashboard_service
from core.constants import AgentStatus


def test_company_roster_includes_all_implemented_employees() -> None:
    """Construct all current employees from their concrete classes."""

    roster = create_company_roster()

    assert len(roster.employees) == 40
    assert {employee.job_title for employee in roster.executives} == {
        "Chief Executive Officer",
        "Chief Operating Officer",
    }
    assert {employee.job_title for employee in roster.directors} == {
        "Strategy Director",
        "Research Director",
        "Marketing Director",
        "SEO Director",
        "Production Director",
        "Creative Quality Director",
        "Distribution Director",
    }
    assert {employee.job_title for employee in roster.specialists} == {
        "Trend Hunter",
        "SEO Specialist",
        "YouTube Manager",
        "Instagram Manager",
        "TikTok Manager",
        "Trend Analyst",
        "Competitor Analyst",
        "Audience Analyst",
        "Retention Engineer",
        "Thumbnail Analyst",
        "Script Writer",
        "Storyboard Artist",
        "Voice Artist",
        "Thumbnail Designer",
        "Shorts Editor",
        "Video Editor",
        "Production Quality Controller",
        "Hook Architect",
        "Story Director",
        "Motion Designer",
        "Subtitle Designer",
        "Thumbnail Psychologist",
        "Retention Auditor",
        "Factuality Reviewer",
        "YouTube Distribution Specialist",
        "Short-form Distribution Specialist",
        "SEO Publisher",
        "Metadata Specialist",
        "Analytics Engineer",
        "Performance Analyst",
        "Learning Engineer",
    }


def test_company_roster_has_unique_deterministic_agent_ids() -> None:
    """Give every factory result stable, collision-free identities."""

    first = create_company_roster()
    second = create_company_roster()
    first_ids = [employee.agent_id for employee in first.employees]
    second_ids = [employee.agent_id for employee in second.employees]

    assert len(first_ids) == len(set(first_ids))
    assert first_ids == second_ids


def test_demo_service_groups_company_and_counts_statuses() -> None:
    """Expose correct organizational groups and sample status counts."""

    snapshot = create_demo_dashboard_service().build_snapshot()

    assert len(snapshot.executives) == 2
    assert len(snapshot.directors) == 7
    assert len(snapshot.specialists) == 31
    assert all(
        employee.group == EmployeeGroup.EXECUTIVE
        for employee in snapshot.executives
    )
    assert snapshot.employees_working == 4
    assert snapshot.employees_idle == 36
    assert snapshot.employee_status_counts[AgentStatus.WORKING] == 4


def test_demo_service_reports_operating_state_and_activity() -> None:
    """Build active sample state with exact workflow progress."""

    snapshot = create_demo_dashboard_service().build_snapshot()

    assert snapshot.active_missions == 1
    assert snapshot.pending_decisions == 1
    assert snapshot.active_workflows == 1
    assert snapshot.workflows[0].progress_percentage == 50.0
    assert snapshot.missions[0].progress_percentage == 50.0
    assert len(snapshot.activity) >= 3
    assert {event.event_type.value for event in snapshot.activity} >= {
        "mission",
        "decision",
        "workflow",
    }
