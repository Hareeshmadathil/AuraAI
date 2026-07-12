"""
Tests for AuraAI's base employee framework.
"""

from core import (
    AgentStatus,
    DepartmentName,
    JobStatus,
    OperationResult,
    TaskRecord,
)
from agents.base_employee import BaseEmployee


class DemoResearchEmployee(BaseEmployee):
    """Small concrete employee used only for framework testing."""

    def perform_task(
        self,
        task: TaskRecord,
    ) -> OperationResult:
        return OperationResult.ok(
            "Research task completed.",
            data={
                "niches_found": 15,
                "task_title": task.title,
            },
        )


def test_employee_task_lifecycle() -> None:
    """Verify assignment, execution, completion, and release."""

    employee = DemoResearchEmployee(
        name="Nova",
        job_title="Research Analyst",
        department=DepartmentName.RESEARCH,
    )

    task = TaskRecord(
        title="Research profitable niches",
        department=DepartmentName.RESEARCH,
    )

    assert employee.status == AgentStatus.IDLE
    assert employee.can_accept_task is True

    employee.accept_task(task)

    assert employee.status == AgentStatus.WAITING
    assert task.status == JobStatus.QUEUED
    assert task.assigned_agent_id == employee.agent_id

    result = employee.execute_current_task()

    assert result.success is True
    assert employee.status == AgentStatus.COMPLETED
    assert task.status == JobStatus.COMPLETED
    assert task.output_data["niches_found"] == 15

    employee.clear_current_task()

    assert employee.status == AgentStatus.IDLE
    assert employee.current_task is None
    assert employee.can_accept_task is True