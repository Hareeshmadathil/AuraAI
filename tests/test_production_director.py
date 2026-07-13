"""Production Director planning and lifecycle tests."""

from agents.base_employee import BaseEmployee
from agents.directors import ProductionDirector, ProductionPlan
from company_missions.fixtures import create_sample_production_input
from core import AgentStatus, DepartmentName, JobStatus, TaskRecord


def test_director_inherits_employee_and_creates_ordered_plan() -> None:
    director = ProductionDirector()
    assert isinstance(director, BaseEmployee)
    assert director.department == DepartmentName.PRODUCTION
    task = TaskRecord(
        title="Plan production",
        input_data={"production_input": create_sample_production_input()},
    )
    director.accept_task(task)
    result = director.execute_current_task()
    plan = ProductionPlan.model_validate(result.data["production_plan"])
    assert result.success
    assert [item.sequence_number for item in plan.assignments] == list(range(1, 8))
    assert len(result.data["generated_tasks"]) == 7
    assert all(item["department"] == "production" for item in result.data["generated_tasks"])
    assert plan.assignments[-1].dependency_assignment_ids
    director.clear_current_task()
    assert director.current_task is None
    assert director.status == AgentStatus.IDLE
    assert task.status == JobStatus.COMPLETED


def test_director_rejects_incomplete_input() -> None:
    director = ProductionDirector()
    task = TaskRecord(title="Invalid plan", input_data={})
    director.accept_task(task)
    result = director.execute_current_task()
    assert not result.success
    assert task.status == JobStatus.FAILED
    director.clear_current_task()
