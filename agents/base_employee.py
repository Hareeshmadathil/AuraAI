"""
Base employee framework for AuraAI Creator OS.

Every AuraAI executive, director, manager, analyst, and specialist will
inherit from ``BaseEmployee``. The class provides a consistent lifecycle
for identity, task assignment, execution, status changes, logging,
retries, failures, and structured results.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Final
from uuid import UUID

from core import (
    AgentError,
    AgentIdentity,
    AgentStatus,
    AuraAIError,
    DepartmentName,
    JobStatus,
    OperationResult,
    PermissionDeniedError,
    TaskRecord,
    get_logger,
    log_exception,
)

if TYPE_CHECKING:
    from providers.models import ProviderCapability, ProviderOutput
    from providers.prompt_template import ProviderPrompt
    from providers.provider_result import ProviderResult
    from providers.router import ProviderRouter


_TERMINAL_TASK_STATUSES: Final[set[JobStatus]] = {
    JobStatus.COMPLETED,
    JobStatus.FAILED,
    JobStatus.CANCELLED,
}


class BaseEmployee(ABC):
    """
    Abstract parent class for every AuraAI employee.

    Subclasses must implement ``perform_task`` with the work specific to
    that employee. Task lifecycle management remains centralized here so
    every employee behaves consistently.
    """

    def __init__(
        self,
        *,
        name: str,
        job_title: str,
        department: DepartmentName,
        description: str = "",
        supervisor_agent_id: UUID | None = None,
        enabled: bool = True,
    ) -> None:
        """
        Create a new AuraAI employee.

        Args:
            name:
                Employee display name.
            job_title:
                Official role inside AuraAI.
            department:
                Department where the employee works.
            description:
                Summary of responsibilities.
            supervisor_agent_id:
                Optional identifier of the supervising employee.
            enabled:
                Whether the employee may receive work.
        """

        initial_status = (
            AgentStatus.IDLE
            if enabled
            else AgentStatus.DISABLED
        )

        self.identity = AgentIdentity(
            name=name,
            job_title=job_title,
            department=department,
            description=description,
            supervisor_agent_id=supervisor_agent_id,
            status=initial_status,
            enabled=enabled,
        )

        self._current_task: TaskRecord | None = None
        self._last_result: OperationResult | None = None
        self._provider_router: ProviderRouter | None = None

        logger_name = (
            f"employee."
            f"{department.value}."
            f"{self.__class__.__name__}"
        )
        self.logger = get_logger(logger_name)

        self.logger.info(
            "Employee initialized: %s (%s)",
            self.name,
            self.job_title,
        )

    @property
    def agent_id(self) -> UUID:
        """Return the employee's permanent identifier."""

        return self.identity.agent_id

    @property
    def name(self) -> str:
        """Return the employee's name."""

        return self.identity.name

    @property
    def job_title(self) -> str:
        """Return the employee's official job title."""

        return self.identity.job_title

    @property
    def department(self) -> DepartmentName:
        """Return the employee's department."""

        return self.identity.department

    @property
    def status(self) -> AgentStatus:
        """Return the employee's current runtime status."""

        return self.identity.status

    @property
    def enabled(self) -> bool:
        """Return whether the employee is enabled."""

        return self.identity.enabled

    @property
    def current_task(self) -> TaskRecord | None:
        """Return the employee's currently assigned task."""

        return self._current_task

    @property
    def last_result(self) -> OperationResult | None:
        """Return the most recent operation result."""

        return self._last_result

    @property
    def has_active_task(self) -> bool:
        """Return whether the employee currently holds unfinished work."""

        if self._current_task is None:
            return False

        return self._current_task.status not in _TERMINAL_TASK_STATUSES

    @property
    def can_accept_task(self) -> bool:
        """Return whether the employee may accept new work."""

        return (
            self.enabled
            and not self.has_active_task
            and self.status
            not in {
                AgentStatus.WORKING,
                AgentStatus.PAUSED,
                AgentStatus.DISABLED,
            }
        )

    @property
    def provider_enabled(self) -> bool:
        """Return whether an explicit provider router was injected."""

        return self._provider_router is not None

    def configure_provider_router(self, router: ProviderRouter | None) -> None:
        """Inject or disable routing without changing employee identity."""

        self._provider_router = router

    def request_provider(
        self,
        capability: ProviderCapability,
        prompt: ProviderPrompt,
    ) -> ProviderResult[ProviderOutput] | None:
        """Request optional typed advice while preserving local behavior."""

        if self._provider_router is None:
            return None
        return self._provider_router.route(capability, prompt)

    def set_status(self, status: AgentStatus) -> None:
        """
        Update the employee status and write the change to the log.
        """

        previous_status = self.identity.status
        self.identity.set_status(status)

        self.logger.info(
            "Employee status changed: %s -> %s",
            previous_status.value,
            status.value,
        )

    def enable(self) -> None:
        """Enable the employee and make them available for work."""

        self.identity.enabled = True
        self.set_status(AgentStatus.IDLE)

        self.logger.info(
            "Employee enabled: %s",
            self.name,
        )

    def disable(self) -> None:
        """
        Disable the employee.

        Raises:
            AgentError:
                If the employee is currently working on an active task.
        """

        if self.has_active_task:
            raise AgentError(
                "An employee with an active task cannot be disabled.",
                agent_name=self.name,
                task_id=str(self._current_task.task_id),
            )

        self.identity.enabled = False
        self.set_status(AgentStatus.DISABLED)

        self.logger.info(
            "Employee disabled: %s",
            self.name,
        )

    def accept_task(self, task: TaskRecord) -> None:
        """
        Assign a task to this employee.

        Args:
            task:
                Task that should be accepted.

        Raises:
            PermissionDeniedError:
                If the task belongs to another employee.
            AgentError:
                If the employee is disabled or already busy.
        """

        if not self.enabled:
            raise AgentError(
                "Disabled employees cannot accept tasks.",
                agent_name=self.name,
                task_id=str(task.task_id),
            )

        if self.has_active_task:
            raise AgentError(
                "Employee already has an active task.",
                agent_name=self.name,
                task_id=str(self._current_task.task_id),
            )

        if (
            task.assigned_agent_id is not None
            and task.assigned_agent_id != self.agent_id
        ):
            raise PermissionDeniedError(
                "The task is assigned to a different employee.",
                details={
                    "task_id": str(task.task_id),
                    "employee_id": str(self.agent_id),
                    "assigned_agent_id": str(
                        task.assigned_agent_id
                    ),
                },
            )

        task.assigned_agent_id = self.agent_id

        if task.department is None:
            task.department = self.department

        task.mark_queued()

        self._current_task = task
        self._last_result = None
        self.set_status(AgentStatus.WAITING)

        self.logger.info(
            "Task accepted: %s | task_id=%s",
            task.title,
            task.task_id,
        )

    def execute_current_task(self) -> OperationResult:
        """
        Execute the currently assigned task.

        Returns:
            Structured operation result returned by the employee.

        Raises:
            AgentError:
                If there is no assigned task.
        """

        if self._current_task is None:
            raise AgentError(
                "Employee has no assigned task to execute.",
                agent_name=self.name,
            )

        task = self._current_task

        if task.status in _TERMINAL_TASK_STATUSES:
            raise AgentError(
                "A completed, failed, or cancelled task cannot run again.",
                agent_name=self.name,
                task_id=str(task.task_id),
            )

        task.mark_running()
        self.set_status(AgentStatus.WORKING)

        self.logger.info(
            "Task execution started: %s | task_id=%s",
            task.title,
            task.task_id,
        )

        try:
            result = self.perform_task(task)

            if not isinstance(result, OperationResult):
                raise AgentError(
                    "perform_task must return an OperationResult.",
                    agent_name=self.name,
                    task_id=str(task.task_id),
                )

            self._last_result = result

            if result.success:
                task.mark_completed(result.data)
                self.set_status(AgentStatus.COMPLETED)

                self.logger.info(
                    "Task completed successfully: %s | task_id=%s",
                    task.title,
                    task.task_id,
                )

                return result

            return self._handle_failed_result(task, result)

        except AuraAIError as error:
            return self._handle_application_error(task, error)

        except Exception as error:
            return self._handle_unexpected_error(task, error)

    def _handle_failed_result(
        self,
        task: TaskRecord,
        result: OperationResult,
    ) -> OperationResult:
        """Handle a normal failed result returned by an employee."""

        if result.retryable and task.can_retry:
            task.register_retry()
            self.set_status(AgentStatus.WAITING)

            self.logger.warning(
                "Task queued for retry: %s | retry=%s/%s",
                task.title,
                task.retry_count,
                task.maximum_retries,
            )

            return result

        task.mark_failed(result.message)
        self.set_status(AgentStatus.FAILED)

        self.logger.error(
            "Task failed: %s | task_id=%s | error=%s",
            task.title,
            task.task_id,
            result.message,
        )

        return result

    def _handle_application_error(
        self,
        task: TaskRecord,
        error: AuraAIError,
    ) -> OperationResult:
        """Handle an expected AuraAI exception."""

        result = OperationResult.failure(
            str(error),
            error_code=error.error_code,
            retryable=error.retryable,
            data=error.details,
        )

        self._last_result = result

        log_exception(
            self.logger,
            (
                f"AuraAI employee error while executing "
                f"task {task.task_id}"
            ),
            exc_info=error,
        )

        return self._handle_failed_result(task, result)

    def _handle_unexpected_error(
        self,
        task: TaskRecord,
        error: Exception,
    ) -> OperationResult:
        """Handle an unexpected Python exception safely."""

        result = OperationResult.failure(
            "An unexpected employee error occurred.",
            error_code="UNEXPECTED_EMPLOYEE_ERROR",
            retryable=False,
            data={
                "exception_type": error.__class__.__name__,
            },
        )

        self._last_result = result
        task.mark_failed(str(error))
        self.set_status(AgentStatus.FAILED)

        log_exception(
            self.logger,
            (
                f"Unexpected error while employee {self.name} "
                f"executed task {task.task_id}"
            ),
            exc_info=error,
        )

        return result

    def clear_current_task(self) -> None:
        """
        Release a terminal task and return the employee to idle status.

        Raises:
            AgentError:
                If the current task is still active.
        """

        if self._current_task is None:
            self.set_status(AgentStatus.IDLE)
            return

        if self._current_task.status not in _TERMINAL_TASK_STATUSES:
            raise AgentError(
                "An active task cannot be cleared.",
                agent_name=self.name,
                task_id=str(self._current_task.task_id),
            )

        completed_task_id = self._current_task.task_id
        self._current_task = None
        self.set_status(AgentStatus.IDLE)

        self.logger.info(
            "Task released: task_id=%s",
            completed_task_id,
        )

    @abstractmethod
    def perform_task(
        self,
        task: TaskRecord,
    ) -> OperationResult:
        """
        Perform employee-specific work.

        Every concrete employee must implement this method.

        Args:
            task:
                Assigned task currently being executed.

        Returns:
            Structured operation result.
        """

        raise NotImplementedError
