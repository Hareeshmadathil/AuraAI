"""
Employee registry for AuraAI Creator OS.

The registry is AuraAI's official company directory. It stores active
employee instances, prevents duplicate registrations, and allows the
orchestrator, departments, workflows, APIs, and dashboard to locate
employees by identifier, role, department, or availability.
"""

from __future__ import annotations

from collections.abc import Iterable
from threading import RLock
from uuid import UUID

from agents.base_employee import BaseEmployee
from core import (
    AgentError,
    AgentStatus,
    DepartmentName,
    get_logger,
)


class EmployeeRegistry:
    """
    Thread-safe in-memory directory of AuraAI employees.

    A database-backed repository can be introduced later without
    changing how the rest of AuraAI searches for employees.
    """

    def __init__(self) -> None:
        self._employees_by_id: dict[UUID, BaseEmployee] = {}
        self._lock = RLock()
        self.logger = get_logger("employee_registry")

    def register(self, employee: BaseEmployee) -> None:
        """
        Register one employee.

        Raises:
            AgentError:
                If the employee is already registered or another
                employee uses the same department and job title.
        """

        with self._lock:
            if employee.agent_id in self._employees_by_id:
                raise AgentError(
                    "Employee is already registered.",
                    agent_name=employee.name,
                    details={
                        "agent_id": str(employee.agent_id),
                    },
                )

            duplicate_role = self.find_by_role(
                employee.job_title,
                department=employee.department,
            )

            if duplicate_role is not None:
                raise AgentError(
                    "An employee with this department and job title "
                    "is already registered.",
                    agent_name=employee.name,
                    details={
                        "department": employee.department.value,
                        "job_title": employee.job_title,
                        "existing_agent_id": str(
                            duplicate_role.agent_id
                        ),
                    },
                )

            self._employees_by_id[employee.agent_id] = employee

            self.logger.info(
                "Employee registered: %s | role=%s | department=%s "
                "| agent_id=%s",
                employee.name,
                employee.job_title,
                employee.department.value,
                employee.agent_id,
            )

    def register_many(
        self,
        employees: Iterable[BaseEmployee],
    ) -> None:
        """
        Register multiple employees one at a time.

        Registration stops immediately when one employee is invalid.
        """

        for employee in employees:
            self.register(employee)

    def unregister(self, agent_id: UUID) -> BaseEmployee:
        """
        Remove and return an employee.

        Raises:
            AgentError:
                If the employee does not exist or has active work.
        """

        with self._lock:
            employee = self.get(agent_id)

            if employee.has_active_task:
                raise AgentError(
                    "An employee with an active task cannot be "
                    "unregistered.",
                    agent_name=employee.name,
                    task_id=str(employee.current_task.task_id),
                )

            removed = self._employees_by_id.pop(agent_id)

            self.logger.info(
                "Employee unregistered: %s | agent_id=%s",
                removed.name,
                removed.agent_id,
            )

            return removed

    def get(self, agent_id: UUID) -> BaseEmployee:
        """
        Return an employee by identifier.

        Raises:
            AgentError:
                If no employee exists with the supplied identifier.
        """

        with self._lock:
            try:
                return self._employees_by_id[agent_id]
            except KeyError as error:
                raise AgentError(
                    "Employee was not found in the registry.",
                    details={
                        "agent_id": str(agent_id),
                    },
                ) from error

    def find_by_name(
        self,
        name: str,
    ) -> list[BaseEmployee]:
        """Return employees whose names match case-insensitively."""

        normalized_name = name.strip().casefold()

        with self._lock:
            return [
                employee
                for employee in self._employees_by_id.values()
                if employee.name.casefold() == normalized_name
            ]

    def find_by_role(
        self,
        job_title: str,
        *,
        department: DepartmentName | None = None,
    ) -> BaseEmployee | None:
        """
        Return the first employee matching a role and optional department.
        """

        normalized_title = job_title.strip().casefold()

        with self._lock:
            for employee in self._employees_by_id.values():
                if employee.job_title.casefold() != normalized_title:
                    continue

                if (
                    department is not None
                    and employee.department != department
                ):
                    continue

                return employee

        return None

    def list_all(self) -> list[BaseEmployee]:
        """Return all registered employees."""

        with self._lock:
            return list(self._employees_by_id.values())

    def list_by_department(
        self,
        department: DepartmentName,
    ) -> list[BaseEmployee]:
        """Return all employees within one department."""

        with self._lock:
            return [
                employee
                for employee in self._employees_by_id.values()
                if employee.department == department
            ]

    def list_by_status(
        self,
        status: AgentStatus,
    ) -> list[BaseEmployee]:
        """Return all employees currently in the supplied status."""

        with self._lock:
            return [
                employee
                for employee in self._employees_by_id.values()
                if employee.status == status
            ]

    def list_available(
        self,
        *,
        department: DepartmentName | None = None,
    ) -> list[BaseEmployee]:
        """
        Return employees that can currently accept a task.

        Args:
            department:
                Optionally restrict results to one department.
        """

        with self._lock:
            employees = self._employees_by_id.values()

            return [
                employee
                for employee in employees
                if employee.can_accept_task
                and (
                    department is None
                    or employee.department == department
                )
            ]

    def contains(self, agent_id: UUID) -> bool:
        """Return whether an employee identifier is registered."""

        with self._lock:
            return agent_id in self._employees_by_id

    def count(
        self,
        *,
        department: DepartmentName | None = None,
    ) -> int:
        """Return total employees or the count within one department."""

        if department is None:
            with self._lock:
                return len(self._employees_by_id)

        return len(self.list_by_department(department))

    def clear(self) -> None:
        """
        Remove all employees that do not have active work.

        Raises:
            AgentError:
                If at least one employee currently has an active task.
        """

        with self._lock:
            busy_employees = [
                employee
                for employee in self._employees_by_id.values()
                if employee.has_active_task
            ]

            if busy_employees:
                raise AgentError(
                    "The registry cannot be cleared while employees "
                    "have active tasks.",
                    details={
                        "busy_employee_ids": [
                            str(employee.agent_id)
                            for employee in busy_employees
                        ],
                    },
                )

            self._employees_by_id.clear()
            self.logger.info("Employee registry cleared.")


employee_registry = EmployeeRegistry()