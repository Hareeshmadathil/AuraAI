"""Shared employee lifecycle helpers for Distribution and Analytics."""

from __future__ import annotations

from collections.abc import Iterable

from agents.base_employee import BaseEmployee
from core import OperationResult, TaskRecord
from runtime_engine.models import RuntimeMode
from runtime_engine.state_manager import RuntimeStateManager


def register_runtime_employees(
    state: RuntimeStateManager,
    employees: Iterable[BaseEmployee],
) -> None:
    """Start an isolated runtime and register missing employees."""

    if state.mode == RuntimeMode.STOPPED:
        state.start_runtime()
    known = {item.agent_id for item in state.list_employee_states()}
    for employee in employees:
        if employee.agent_id not in known:
            state.register_employee(employee)


def execute_employee_task(
    employee: BaseEmployee,
    task: TaskRecord,
) -> OperationResult:
    """Execute one task through the standard lifecycle and release it."""

    try:
        employee.accept_task(task)
        return employee.execute_current_task()
    except Exception as error:
        return OperationResult.failure(
            "Employee lifecycle execution failed.",
            error_code="EMPLOYEE_LIFECYCLE_ERROR",
            data={"exception_type": error.__class__.__name__},
        )
    finally:
        if employee.current_task is not None and not employee.has_active_task:
            employee.clear_current_task()
