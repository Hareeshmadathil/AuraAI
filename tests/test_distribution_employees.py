from agents.base_employee import BaseEmployee
from agents.directors import DistributionDirector
from agents.specialists import (
    AnalyticsEngineer,
    LearningEngineer,
    MetadataSpecialist,
    PerformanceAnalyst,
    SEOPublisher,
    ShortFormDistributionSpecialist,
    YouTubeDistributionSpecialist,
)
from analytics.providers import DeterministicAnalyticsProvider
from core import DepartmentName, TaskRecord
from distribution.models import DistributionPlan


def test_all_distribution_and_analytics_employees_inherit_base_employee() -> None:
    provider = DeterministicAnalyticsProvider()
    employees = (
        DistributionDirector(),
        YouTubeDistributionSpecialist(),
        ShortFormDistributionSpecialist(),
        SEOPublisher(),
        MetadataSpecialist(),
        AnalyticsEngineer(provider),
        PerformanceAnalyst(),
        LearningEngineer(provider),
    )

    assert all(isinstance(employee, BaseEmployee) for employee in employees)
    assert all(
        employee.department in {
            DepartmentName.DISTRIBUTION,
            DepartmentName.ANALYTICS,
        }
        for employee in employees
    )


def test_distribution_director_preserves_base_employee_lifecycle() -> None:
    director = DistributionDirector()
    task = TaskRecord(
        title="Plan distribution",
        department=DepartmentName.DISTRIBUTION,
        input_data={"source_package_id": "b5fc49c5-551c-47a4-b296-f90ce871a398"},
    )

    director.accept_task(task)
    result = director.execute_current_task()

    assert result.success
    assert DistributionPlan.model_validate(result.data["distribution_plan"])
    assert task.status.value == "completed"
    director.clear_current_task()
    assert director.current_task is None
