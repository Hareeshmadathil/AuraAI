"""
Base workflow engine for AuraAI Creator OS.

A workflow converts an approved company mission into an ordered set of
operational steps. Each step may belong to a department, depend on
earlier steps, require approval, create employee tasks, retry failures,
and report progress back to AuraAI leadership.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from core.constants import (
    ApprovalStatus,
    DepartmentName,
    JobStatus,
)
from core.exceptions import WorkflowError
from core.logger import get_logger
from core.models import (
    AuraBaseModel,
    TaskRecord,
    WorkflowRecord,
    utc_now,
)


_TERMINAL_STEP_STATUSES = {
    JobStatus.COMPLETED,
    JobStatus.FAILED,
    JobStatus.CANCELLED,
}


class WorkflowStep(AuraBaseModel):
    """
    One operational step inside an AuraAI workflow.

    A step may later create one or more employee tasks, but it remains
    responsible for workflow-level dependencies and approval state.
    """

    step_id: UUID = Field(default_factory=uuid4)

    name: str = Field(
        min_length=1,
        max_length=200,
    )

    description: str = Field(
        default="",
        max_length=5000,
    )

    department: DepartmentName

    status: JobStatus = JobStatus.CREATED

    dependency_step_ids: list[UUID] = Field(default_factory=list)

    assigned_agent_id: UUID | None = None

    task_id: UUID | None = None

    requires_approval: bool = False

    approval_status: ApprovalStatus = ApprovalStatus.NOT_REQUIRED

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

    @model_validator(mode="before")
    @classmethod
    def normalize_step_configuration(
        cls,
        values: Any,
    ) -> Any:
        """
        Normalize approval configuration before model creation.

        This validator operates on the incoming dictionary instead of
        assigning values back to the validated model. That prevents
        recursive validation when Pydantic assignment validation is
        enabled.
        """

        if not isinstance(values, dict):
            return values

        normalized_values = dict(values)

        requires_approval = bool(
            normalized_values.get(
                "requires_approval",
                False,
            )
        )

        current_approval_status = normalized_values.get(
            "approval_status",
            ApprovalStatus.NOT_REQUIRED,
        )

        if requires_approval:
            if current_approval_status in {
                ApprovalStatus.NOT_REQUIRED,
                ApprovalStatus.NOT_REQUIRED.value,
                None,
            }:
                normalized_values["approval_status"] = (
                    ApprovalStatus.PENDING
                )
        else:
            normalized_values["approval_status"] = (
                ApprovalStatus.NOT_REQUIRED
            )

        return normalized_values

    @model_validator(mode="after")
    def validate_step_configuration(self) -> "WorkflowStep":
        """
        Validate retry values and dependency relationships.

        This validator performs checks only. It does not mutate model
        fields, which avoids recursive assignment validation.
        """

        if self.retry_count > self.maximum_retries:
            raise ValueError(
                "retry_count cannot be greater than maximum_retries."
            )

        if self.step_id in self.dependency_step_ids:
            raise ValueError(
                "A workflow step cannot depend on itself."
            )

        return self

    @property
    def is_terminal(self) -> bool:
        """Return whether this step has reached a final state."""

        return self.status in _TERMINAL_STEP_STATUSES

    @property
    def can_retry(self) -> bool:
        """Return whether retry attempts remain."""

        return self.retry_count < self.maximum_retries

    @property
    def is_approved(self) -> bool:
        """Return whether approval permits this step to run."""

        return self.approval_status in {
            ApprovalStatus.APPROVED,
            ApprovalStatus.NOT_REQUIRED,
        }

    def dependencies_completed(
        self,
        completed_step_ids: set[UUID],
    ) -> bool:
        """Return whether all dependency steps are completed."""

        return all(
            dependency_id in completed_step_ids
            for dependency_id in self.dependency_step_ids
        )

    def approve(self) -> None:
        """Approve a step requiring executive or user approval."""

        if not self.requires_approval:
            self.approval_status = ApprovalStatus.NOT_REQUIRED
            self.updated_at = utc_now()
            return

        if self.is_terminal:
            raise ValueError(
                "A terminal workflow step cannot be approved."
            )

        self.approval_status = ApprovalStatus.APPROVED
        self.updated_at = utc_now()

    def reject(self, reason: str) -> None:
        """Reject a pending step and mark it as failed."""

        clean_reason = reason.strip()

        if not clean_reason:
            raise ValueError(
                "A rejection reason is required."
            )

        if self.is_terminal:
            raise ValueError(
                "A terminal workflow step cannot be rejected."
            )

        self.approval_status = ApprovalStatus.REJECTED
        self.status = JobStatus.FAILED
        self.error_message = clean_reason
        self.completed_at = utc_now()
        self.updated_at = utc_now()

    def mark_queued(self) -> None:
        """Place the step into the execution queue."""

        if self.is_terminal:
            raise ValueError(
                "A terminal workflow step cannot be queued."
            )

        self.status = JobStatus.QUEUED
        self.updated_at = utc_now()

    def mark_running(self) -> None:
        """Mark the step as actively running."""

        if not self.is_approved:
            raise ValueError(
                "The workflow step requires approval before running."
            )

        if self.is_terminal:
            raise ValueError(
                "A terminal workflow step cannot run."
            )

        self.status = JobStatus.RUNNING
        self.started_at = self.started_at or utc_now()
        self.updated_at = utc_now()

    def mark_completed(
        self,
        output_data: dict[str, Any] | None = None,
    ) -> None:
        """Mark the step as completed successfully."""

        if self.status != JobStatus.RUNNING:
            raise ValueError(
                "Only a running workflow step can be completed."
            )

        self.status = JobStatus.COMPLETED
        self.output_data = output_data or {}
        self.error_message = None
        self.completed_at = utc_now()
        self.updated_at = utc_now()

    def mark_failed(
        self,
        error_message: str,
    ) -> None:
        """Mark the step as failed."""

        clean_message = error_message.strip()

        if not clean_message:
            raise ValueError(
                "A failure message is required."
            )

        if self.is_terminal:
            raise ValueError(
                "A terminal workflow step cannot fail again."
            )

        self.status = JobStatus.FAILED
        self.error_message = clean_message
        self.completed_at = utc_now()
        self.updated_at = utc_now()

    def register_retry(self) -> None:
        """Requeue a failed step when retry attempts remain."""

        if self.status != JobStatus.FAILED:
            raise ValueError(
                "Only a failed workflow step can be retried."
            )

        if not self.can_retry:
            raise ValueError(
                "Maximum retry count has been reached."
            )

        self.retry_count += 1
        self.status = JobStatus.QUEUED
        self.error_message = None
        self.completed_at = None
        self.updated_at = utc_now()

    def create_task(self) -> TaskRecord:
        """
        Create an employee task for this workflow step.

        Returns:
            A new TaskRecord linked to this step.
        """

        if self.task_id is not None:
            raise ValueError(
                "This workflow step already has a task."
            )

        task = TaskRecord(
            title=self.name,
            description=self.description,
            assigned_agent_id=self.assigned_agent_id,
            department=self.department,
            input_data=dict(self.input_data),
            maximum_retries=self.maximum_retries,
        )

        self.task_id = task.task_id
        self.updated_at = utc_now()

        return task


class BaseWorkflow(ABC):
    """
    Abstract parent class for every AuraAI workflow.

    Subclasses define their steps inside ``build_steps``. This base
    class manages ordering, dependencies, progress, retries, execution
    state, and workflow completion.
    """

    def __init__(
        self,
        *,
        name: str,
        description: str = "",
        mission_id: UUID | None = None,
    ) -> None:
        self.record = WorkflowRecord(
            name=name,
            description=description,
            context={
                "mission_id": (
                    str(mission_id)
                    if mission_id is not None
                    else None
                ),
            },
        )

        self.mission_id = mission_id
        self._steps: dict[UUID, WorkflowStep] = {}

        self.logger = get_logger(
            f"workflow.{self.__class__.__name__}"
        )

        self.build_steps()
        self._validate_workflow()

        self.logger.info(
            "Workflow initialized: %s | workflow_id=%s | steps=%s",
            self.name,
            self.workflow_id,
            len(self._steps),
        )

    @property
    def workflow_id(self) -> UUID:
        """Return the workflow identifier."""

        return self.record.workflow_id

    @property
    def name(self) -> str:
        """Return the workflow name."""

        return self.record.name

    @property
    def status(self) -> JobStatus:
        """Return the workflow status."""

        return self.record.status

    @property
    def steps(self) -> list[WorkflowStep]:
        """Return workflow steps in insertion order."""

        return list(self._steps.values())

    @property
    def completed_step_ids(self) -> set[UUID]:
        """Return identifiers of completed workflow steps."""

        return {
            step.step_id
            for step in self._steps.values()
            if step.status == JobStatus.COMPLETED
        }

    @property
    def progress_percentage(self) -> float:
        """Return completion progress based on workflow steps."""

        if not self._steps:
            return 0.0

        completed_count = len(self.completed_step_ids)

        return round(
            completed_count / len(self._steps) * 100,
            2,
        )

    @property
    def is_complete(self) -> bool:
        """Return whether all workflow steps are complete."""

        return bool(self._steps) and all(
            step.status == JobStatus.COMPLETED
            for step in self._steps.values()
        )

    @abstractmethod
    def build_steps(self) -> None:
        """
        Define workflow steps.

        Subclasses must call ``add_step`` for every operational step.
        """

        raise NotImplementedError

    def add_step(
        self,
        *,
        name: str,
        department: DepartmentName,
        description: str = "",
        dependency_step_ids: list[UUID] | None = None,
        requires_approval: bool = False,
        maximum_retries: int = 3,
        input_data: dict[str, Any] | None = None,
    ) -> WorkflowStep:
        """Create and attach one workflow step."""

        step = WorkflowStep(
            name=name,
            description=description,
            department=department,
            dependency_step_ids=list(
                dependency_step_ids or []
            ),
            requires_approval=requires_approval,
            maximum_retries=maximum_retries,
            input_data=input_data or {},
        )

        self._steps[step.step_id] = step
        self.record.add_task(step.step_id)

        return step

    def get_step(self, step_id: UUID) -> WorkflowStep:
        """Return one step by identifier."""

        try:
            return self._steps[step_id]
        except KeyError as error:
            raise WorkflowError(
                "Workflow step was not found.",
                workflow_name=self.name,
                job_id=str(self.workflow_id),
                details={
                    "step_id": str(step_id),
                },
            ) from error

    def start(self) -> None:
        """Start the workflow."""

        if not self._steps:
            raise WorkflowError(
                "A workflow cannot start without steps.",
                workflow_name=self.name,
                job_id=str(self.workflow_id),
            )

        if self.status not in {
            JobStatus.CREATED,
            JobStatus.PAUSED,
        }:
            raise WorkflowError(
                "The workflow cannot start from its current status.",
                workflow_name=self.name,
                job_id=str(self.workflow_id),
                details={
                    "status": self.status.value,
                },
            )

        self.record.mark_running()

        self.logger.info(
            "Workflow started: %s | workflow_id=%s",
            self.name,
            self.workflow_id,
        )

    def get_ready_steps(self) -> list[WorkflowStep]:
        """
        Return steps ready for task creation or execution.

        A ready step:
        - has not already completed or failed,
        - has all dependencies completed,
        - and has any required approval.
        """

        completed_ids = self.completed_step_ids

        return [
            step
            for step in self._steps.values()
            if step.status in {
                JobStatus.CREATED,
                JobStatus.QUEUED,
            }
            and step.dependencies_completed(completed_ids)
            and step.is_approved
        ]

    def start_step(self, step_id: UUID) -> WorkflowStep:
        """Start one ready workflow step."""

        if self.status != JobStatus.RUNNING:
            raise WorkflowError(
                "The workflow must be running before a step can start.",
                workflow_name=self.name,
                job_id=str(self.workflow_id),
            )

        step = self.get_step(step_id)

        if step not in self.get_ready_steps():
            raise WorkflowError(
                "The workflow step is not ready to start.",
                workflow_name=self.name,
                job_id=str(self.workflow_id),
                details={
                    "step_id": str(step_id),
                },
            )

        step.mark_running()
        self.record.current_task_id = step.step_id
        self.record.updated_at = utc_now()

        self.logger.info(
            "Workflow step started: %s | step_id=%s",
            step.name,
            step.step_id,
        )

        return step

    def complete_step(
        self,
        step_id: UUID,
        *,
        output_data: dict[str, Any] | None = None,
    ) -> WorkflowStep:
        """Complete one running step and update workflow progress."""

        step = self.get_step(step_id)
        step.mark_completed(output_data)

        self.record.current_task_id = None
        self.record.updated_at = utc_now()

        self.logger.info(
            "Workflow step completed: %s | step_id=%s",
            step.name,
            step.step_id,
        )

        if self.is_complete:
            self.record.mark_completed()

            self.logger.info(
                "Workflow completed: %s | workflow_id=%s",
                self.name,
                self.workflow_id,
            )

        return step

    def fail_step(
        self,
        step_id: UUID,
        *,
        error_message: str,
        retryable: bool = False,
    ) -> WorkflowStep:
        """Fail a step, optionally placing it back into the queue."""

        step = self.get_step(step_id)
        step.mark_failed(error_message)

        self.record.current_task_id = None
        self.record.updated_at = utc_now()

        if retryable and step.can_retry:
            step.register_retry()

            self.logger.warning(
                "Workflow step queued for retry: %s | retry=%s/%s",
                step.name,
                step.retry_count,
                step.maximum_retries,
            )

            return step

        self.record.mark_failed(error_message)

        self.logger.error(
            "Workflow failed at step: %s | error=%s",
            step.name,
            error_message,
        )

        return step

    def _validate_workflow(self) -> None:
        """Validate dependencies and detect circular relationships."""

        if not self._steps:
            raise WorkflowError(
                "A workflow definition must contain at least one step.",
                workflow_name=self.name,
                job_id=str(self.workflow_id),
            )

        known_step_ids = set(self._steps)

        for step in self._steps.values():
            missing_dependencies = [
                dependency_id
                for dependency_id in step.dependency_step_ids
                if dependency_id not in known_step_ids
            ]

            if missing_dependencies:
                raise WorkflowError(
                    "Workflow step contains unknown dependencies.",
                    workflow_name=self.name,
                    job_id=str(self.workflow_id),
                    details={
                        "step_id": str(step.step_id),
                        "missing_dependencies": [
                            str(dependency_id)
                            for dependency_id
                            in missing_dependencies
                        ],
                    },
                )

        visiting: set[UUID] = set()
        visited: set[UUID] = set()

        def visit(step_id: UUID) -> None:
            if step_id in visiting:
                raise WorkflowError(
                    "Circular workflow dependency detected.",
                    workflow_name=self.name,
                    job_id=str(self.workflow_id),
                    details={
                        "step_id": str(step_id),
                    },
                )

            if step_id in visited:
                return

            visiting.add(step_id)

            step = self._steps[step_id]

            for dependency_id in step.dependency_step_ids:
                visit(dependency_id)

            visiting.remove(step_id)
            visited.add(step_id)

        for step_id in known_step_ids:
            visit(step_id)