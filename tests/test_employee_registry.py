"""
Tests for AuraAI's employee registry.
"""

import pytest

from agents.base_employee import BaseEmployee
from agents.employee_registry import EmployeeRegistry
from core import (
    AgentError,
    DepartmentName,
    OperationResult,
    TaskRecord,
)


class DemoEmployee(BaseEmployee):
    """Concrete employee used only for registry tests."""

    def perform_task(
        self,
        task: TaskRecord,
    ) -> OperationResult:
        return OperationResult.ok(
            "Demo task completed.",
            data={"task_title": task.title},
        )


def build_employee(
    *,
    name: str,
    job_title: str,
    department: DepartmentName,
) -> DemoEmployee:
    """Create a test employee."""

    return DemoEmployee(
        name=name,
        job_title=job_title,
        department=department,
    )


def test_registry_registers_and_finds_employees() -> None:
    registry = EmployeeRegistry()

    research_director = build_employee(
        name="Nova",
        job_title="Research Director",
        department=DepartmentName.RESEARCH,
    )

    trend_hunter = build_employee(
        name="Scout",
        job_title="Trend Hunter",
        department=DepartmentName.RESEARCH,
    )

    registry.register_many(
        [research_director, trend_hunter]
    )

    assert registry.count() == 2
    assert registry.count(
        department=DepartmentName.RESEARCH
    ) == 2

    assert registry.get(
        research_director.agent_id
    ) is research_director

    assert registry.find_by_role(
        "Research Director",
        department=DepartmentName.RESEARCH,
    ) is research_director

    assert registry.find_by_name("scout") == [
        trend_hunter
    ]

    assert registry.list_by_department(
        DepartmentName.RESEARCH
    ) == [
        research_director,
        trend_hunter,
    ]

    assert registry.list_available(
        department=DepartmentName.RESEARCH
    ) == [
        research_director,
        trend_hunter,
    ]


def test_registry_rejects_duplicate_roles() -> None:
    registry = EmployeeRegistry()

    first_employee = build_employee(
        name="Nova",
        job_title="Research Director",
        department=DepartmentName.RESEARCH,
    )

    duplicate_role = build_employee(
        name="Orion",
        job_title="Research Director",
        department=DepartmentName.RESEARCH,
    )

    registry.register(first_employee)

    with pytest.raises(AgentError):
        registry.register(duplicate_role)


def test_registry_unregisters_employee() -> None:
    registry = EmployeeRegistry()

    employee = build_employee(
        name="Pulse",
        job_title="Analytics Director",
        department=DepartmentName.ANALYTICS,
    )

    registry.register(employee)

    removed = registry.unregister(
        employee.agent_id
    )

    assert removed is employee
    assert registry.count() == 0
    assert registry.contains(employee.agent_id) is False