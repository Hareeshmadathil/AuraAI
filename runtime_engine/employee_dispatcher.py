"""Single deterministic dispatch boundary for AuraAI employees."""

from __future__ import annotations

from core import AgentError, OperationResult, TaskRecord
from agents.base_employee import BaseEmployee
from agents.employee_registry import EmployeeRegistry
from mission_control.models import DepartmentCommand, DepartmentResult


class EmployeeDispatcher:
    """Translate canonical commands into employee work and correlated results."""

    def __init__(self, registry: EmployeeRegistry) -> None:
        self._registry = registry

    def dispatch(self, command: DepartmentCommand) -> DepartmentResult:
        """Execute one Mission Control command with one eligible employee.

        Args:
            command: The canonical, idempotency-bound command to execute.

        Returns:
            A result correlated to the original command, mission, and task.
        """

        employee = self._select_employee(command)
        task = TaskRecord(
            task_id=command.task_id,
            title=command.operation,
            description=f"Mission Control command {command.command_id}",
            assigned_agent_id=employee.agent_id,
            department=command.department,
            input_data={
                **command.payload,
                "mission_id": str(command.mission_id),
                "command_id": str(command.command_id),
                "idempotency_key": command.idempotency_key,
            },
        )

        try:
            employee.accept_task(task)
            operation_result = employee.execute_current_task()
            return self._to_department_result(command, operation_result)
        except AgentError as error:
            return DepartmentResult(
                command_id=command.command_id,
                mission_id=command.mission_id,
                task_id=command.task_id,
                success=False,
                error_code="EMPLOYEE_DISPATCH_FAILED",
                payload={"message": str(error)},
            )
        finally:
            if employee.current_task is not None and not employee.has_active_task:
                employee.clear_current_task()

    def _select_employee(self, command: DepartmentCommand) -> BaseEmployee:
        available = self._registry.list_available(department=command.department)
        if not available:
            raise AgentError(
                "No available employee is registered for the department.",
                details={"department": command.department.value},
            )
        return min(available, key=lambda employee: str(employee.agent_id))

    @staticmethod
    def _to_department_result(
        command: DepartmentCommand,
        result: OperationResult,
    ) -> DepartmentResult:
        payload = {"message": result.message, **result.data}
        return DepartmentResult(
            command_id=command.command_id,
            mission_id=command.mission_id,
            task_id=command.task_id,
            success=result.success,
            payload=payload,
            error_code=result.error_code,
        )
