from core import AgentStatus, DepartmentName, TaskRecord
from intelligence.pipeline import create_intelligence_pipeline


def test_all_intelligence_employees_use_base_lifecycle() -> None:
    pipeline = create_intelligence_pipeline()

    for employee in pipeline.employees:
        task = TaskRecord(
            title=f"Test {employee.job_title}",
            department=DepartmentName.INTELLIGENCE,
            input_data={"niche": "AI productivity"},
        )
        employee.accept_task(task)
        result = employee.execute_current_task()
        assert result.success is True
        assert task.status.value == "completed"
        assert employee.department == DepartmentName.INTELLIGENCE
        employee.clear_current_task()
        assert employee.status == AgentStatus.IDLE


def test_intelligence_employee_rejects_missing_niche() -> None:
    employee = create_intelligence_pipeline().trend_analyst
    employee.accept_task(
        TaskRecord(
            title="Missing niche",
            department=DepartmentName.INTELLIGENCE,
            input_data={},
        )
    )

    result = employee.execute_current_task()

    assert result.success is False
    assert result.error_code == "VALIDATION_ERROR"
