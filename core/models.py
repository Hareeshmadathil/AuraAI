"""
Shared data models for AuraAI Creator OS.

These models define the common language used by employee-agents,
departments, workflows, services, the future database layer, and the
web dashboard.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.constants import (
    AgentStatus,
    DepartmentName,
    JobStatus,
    TaskPriority,
)


def utc_now() -> datetime:
    """
    Return the current timezone-aware UTC datetime.
    """

    return datetime.now(UTC)


class AuraBaseModel(BaseModel):
    """
    Base class for all AuraAI data models.

    Extra fields are rejected so incorrect or unexpected data cannot
    silently enter the system.
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        use_enum_values=False,
        str_strip_whitespace=True,
    )


class AgentIdentity(AuraBaseModel):
    """
    Permanent identity and organisational role of an AuraAI employee.
    """

    agent_id: UUID = Field(default_factory=uuid4)

    name: str = Field(
        min_length=1,
        max_length=100,
    )

    job_title: str = Field(
        min_length=1,
        max_length=150,
    )

    department: DepartmentName

    description: str = Field(
        default="",
        max_length=1000,
    )

    supervisor_agent_id: UUID | None = None

    status: AgentStatus = AgentStatus.OFFLINE

    enabled: bool = True

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def set_status(self, status: AgentStatus) -> None:
        """
        Update the employee's runtime status and modification time.
        """

        self.status = status
        self.updated_at = utc_now()


class TaskRecord(AuraBaseModel):
    """
    A unit of work assigned to an AuraAI employee or department.
    """

    task_id: UUID = Field(default_factory=uuid4)

    title: str = Field(
        min_length=1,
        max_length=200,
    )

    description: str = Field(
        default="",
        max_length=5000,
    )

    assigned_agent_id: UUID | None = None

    department: DepartmentName | None = None

    priority: TaskPriority = TaskPriority.NORMAL

    status: JobStatus = JobStatus.CREATED

    input_data: dict[str, Any] = Field(default_factory=dict)

    output_data: dict[str, Any] = Field(default_factory=dict)

    error_message: str | None = Field(
        default=None,
        max_length=5000,
    )

    retry_count: int = Field(
        default=0,
        ge=0,
    )

    maximum_retries: int = Field(
        default=3,
        ge=0,
    )

    created_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_retry_values(self) -> "TaskRecord":
        """
        Ensure retry counters remain logically valid.
        """

        if self.retry_count > self.maximum_retries:
            raise ValueError(
                "retry_count cannot be greater than maximum_retries."
            )

        return self

    @property
    def can_retry(self) -> bool:
        """
        Return whether this task has retry attempts remaining.
        """

        return self.retry_count < self.maximum_retries

    def mark_queued(self) -> None:
        """
        Mark the task as waiting to be processed.
        """

        self.status = JobStatus.QUEUED
        self.updated_at = utc_now()

    def mark_running(self) -> None:
        """
        Mark the task as actively running.
        """

        self.status = JobStatus.RUNNING
        self.started_at = self.started_at or utc_now()
        self.updated_at = utc_now()

    def mark_completed(
        self,
        output_data: dict[str, Any] | None = None,
    ) -> None:
        """
        Mark the task as successfully completed.
        """

        self.status = JobStatus.COMPLETED
        self.output_data = output_data or {}
        self.error_message = None
        self.completed_at = utc_now()
        self.updated_at = utc_now()

    def mark_failed(
        self,
        error_message: str,
    ) -> None:
        """
        Mark the task as failed.
        """

        self.status = JobStatus.FAILED
        self.error_message = error_message
        self.updated_at = utc_now()

    def register_retry(self) -> None:
        """
        Increase the retry counter.

        Raises:
            ValueError:
                When no retry attempts remain.
        """

        if not self.can_retry:
            raise ValueError(
                "Maximum retry count has already been reached."
            )

        self.retry_count += 1
        self.status = JobStatus.QUEUED
        self.updated_at = utc_now()


class WorkflowRecord(AuraBaseModel):
    """
    A workflow that coordinates multiple AuraAI tasks.
    """

    workflow_id: UUID = Field(default_factory=uuid4)

    name: str = Field(
        min_length=1,
        max_length=200,
    )

    description: str = Field(
        default="",
        max_length=5000,
    )

    status: JobStatus = JobStatus.CREATED

    task_ids: list[UUID] = Field(default_factory=list)

    current_task_id: UUID | None = None

    context: dict[str, Any] = Field(default_factory=dict)

    error_message: str | None = Field(
        default=None,
        max_length=5000,
    )

    created_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime = Field(default_factory=utc_now)

    def add_task(self, task_id: UUID) -> None:
        """
        Add a task to the workflow when it is not already present.
        """

        if task_id not in self.task_ids:
            self.task_ids.append(task_id)
            self.updated_at = utc_now()

    def mark_running(self) -> None:
        """
        Mark the workflow as active.
        """

        self.status = JobStatus.RUNNING
        self.started_at = self.started_at or utc_now()
        self.updated_at = utc_now()

    def mark_completed(self) -> None:
        """
        Mark the workflow as successfully completed.
        """

        self.status = JobStatus.COMPLETED
        self.error_message = None
        self.completed_at = utc_now()
        self.updated_at = utc_now()

    def mark_failed(self, error_message: str) -> None:
        """
        Mark the workflow as failed.
        """

        self.status = JobStatus.FAILED
        self.error_message = error_message
        self.updated_at = utc_now()


class AgentMessage(AuraBaseModel):
    """
    Structured message exchanged between AuraAI employees.
    """

    message_id: UUID = Field(default_factory=uuid4)

    sender_agent_id: UUID

    recipient_agent_id: UUID | None = None

    recipient_department: DepartmentName | None = None

    subject: str = Field(
        min_length=1,
        max_length=200,
    )

    body: str = Field(
        min_length=1,
        max_length=10000,
    )

    task_id: UUID | None = None

    metadata: dict[str, Any] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_recipient(self) -> "AgentMessage":
        """
        Ensure the message has an employee or department recipient.
        """

        if (
            self.recipient_agent_id is None
            and self.recipient_department is None
        ):
            raise ValueError(
                "A message must have either a recipient_agent_id "
                "or recipient_department."
            )

        return self


class OperationResult(AuraBaseModel):
    """
    Standard result returned by AuraAI services and employee-agents.
    """

    success: bool

    message: str = Field(
        min_length=1,
        max_length=5000,
    )

    data: dict[str, Any] = Field(default_factory=dict)

    error_code: str | None = Field(
        default=None,
        max_length=100,
    )

    retryable: bool = False

    created_at: datetime = Field(default_factory=utc_now)

    @classmethod
    def ok(
        cls,
        message: str,
        *,
        data: dict[str, Any] | None = None,
    ) -> "OperationResult":
        """
        Create a successful operation result.
        """

        return cls(
            success=True,
            message=message,
            data=data or {},
            retryable=False,
        )

    @classmethod
    def failure(
        cls,
        message: str,
        *,
        error_code: str = "OPERATION_FAILED",
        retryable: bool = False,
        data: dict[str, Any] | None = None,
    ) -> "OperationResult":
        """
        Create a failed operation result.
        """

        return cls(
            success=False,
            message=message,
            error_code=error_code,
            retryable=retryable,
            data=data or {},
        )