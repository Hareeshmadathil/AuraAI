"""Deterministic, bounded execution of existing AuraAI workflows."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from agents.base_employee import BaseEmployee
from core import (
    AgentStatus,
    JobStatus,
    MissionRecord,
    MissionStatus,
    OperationResult,
    StorageError,
    ValidationError,
)
from runtime_engine.event_bus import RuntimeEventBus
from runtime_engine.models import (
    RuntimeEventSeverity,
    RuntimeEventType,
)
from runtime_engine.state_manager import RuntimeStateManager
from workflows.base_workflow import BaseWorkflow, WorkflowStep


class MissionRunner:
    def __init__(
        self,
        state_manager: RuntimeStateManager,
        event_bus: RuntimeEventBus,
        employees: Iterable[BaseEmployee] = (),
        *,
        maximum_steps: int = 100,
    ) -> None:
        if maximum_steps <= 0:
            raise ValidationError("maximum_steps must be greater than zero.")
        self.state_manager = state_manager
        self.event_bus = event_bus
        self.maximum_steps = maximum_steps
        self._employees: dict[UUID, BaseEmployee] = {}
        self._paused = False
        self._stopped = False
        for employee in employees:
            self.register_employee(employee)

    def register_employee(self, employee: BaseEmployee) -> None:
        if employee.agent_id in self._employees:
            raise StorageError("Runner employee is already registered.")
        self._employees[employee.agent_id] = employee
        try:
            self.state_manager.register_employee(employee)
        except StorageError:
            pass

    def unregister_employee(self, agent_id: UUID) -> BaseEmployee:
        try:
            return self._employees.pop(agent_id)
        except KeyError as error:
            raise ValidationError("Runner employee was not found.") from error

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False
        self._stopped = False

    def stop(self) -> None:
        self._stopped = True

    def run_workflow(
        self, mission: MissionRecord, workflow: BaseWorkflow
    ) -> OperationResult:
        self._ensure_registered(mission, workflow)
        completed_steps = 0
        while completed_steps < self.maximum_steps:
            result = self.run_next_step(mission, workflow)
            if not result.success or result.data.get("stop_reason"):
                return result
            completed_steps += 1
            if workflow.status == JobStatus.COMPLETED:
                return OperationResult.ok(
                    "Workflow completed.",
                    data={
                        "steps_executed": completed_steps,
                        "stop_reason": "workflow_completed",
                    },
                )
        self.event_bus.emit(
            RuntimeEventType.WARNING,
            "Maximum workflow step limit reached.",
            mission_id=mission.mission_id,
            workflow_id=workflow.workflow_id,
            severity=RuntimeEventSeverity.WARNING,
        )
        return OperationResult.failure(
            "Maximum workflow step limit reached.",
            error_code="MAXIMUM_STEPS_REACHED",
            data={"stop_reason": "maximum_steps"},
        )

    def run_next_step(
        self, mission: MissionRecord, workflow: BaseWorkflow
    ) -> OperationResult:
        if self._stopped:
            return OperationResult.failure(
                "Mission runner is stopped.", error_code="RUNNER_STOPPED"
            )
        if self._paused:
            return OperationResult.failure(
                "Mission runner is paused.", error_code="RUNNER_PAUSED"
            )
        self._ensure_registered(mission, workflow)
        self._start_if_needed(mission, workflow)

        ready_steps = workflow.get_ready_steps()
        if not ready_steps:
            approval_step = self._approval_blocker(workflow)
            if approval_step is not None:
                workflow.record.status = JobStatus.PAUSED
                self.state_manager.update_workflow_state(
                    workflow.workflow_id,
                    status=JobStatus.PAUSED,
                    progress_percentage=workflow.progress_percentage,
                    current_step_id=approval_step.step_id,
                    current_step_name=approval_step.name,
                )
                return OperationResult.failure(
                    "Workflow step requires approval.",
                    error_code="APPROVAL_REQUIRED",
                    data={
                        "step_id": str(approval_step.step_id),
                        "stop_reason": "approval_required",
                    },
                )
            return OperationResult.ok(
                "No workflow step is ready.",
                data={"stop_reason": "no_ready_step"},
            )

        step = ready_steps[0]
        employee = self._resolve_employee(step)
        if employee is None:
            message = f"No eligible employee for {step.department.value}."
            self.event_bus.emit(
                RuntimeEventType.WARNING,
                message,
                mission_id=mission.mission_id,
                workflow_id=workflow.workflow_id,
                department=step.department,
                severity=RuntimeEventSeverity.WARNING,
            )
            return OperationResult.failure(
                message,
                error_code="EMPLOYEE_UNAVAILABLE",
                data={"stop_reason": "employee_unavailable"},
            )

        task = step.create_task()
        workflow.start_step(step.step_id)
        self.event_bus.emit(
            RuntimeEventType.TASK_STARTED,
            f"Task started: {task.title}.",
            mission_id=mission.mission_id,
            workflow_id=workflow.workflow_id,
            task_id=task.task_id,
            agent_id=employee.agent_id,
            agent_name=employee.name,
            department=employee.department,
        )
        employee.accept_task(task)
        self.state_manager.update_employee_state(
            employee.agent_id,
            status=AgentStatus.WORKING,
            current_task_id=task.task_id,
            current_task_title=task.title,
            current_mission_id=mission.mission_id,
        )
        result = employee.execute_current_task()

        if result.success:
            workflow.complete_step(step.step_id, output_data=result.data)
            self.event_bus.emit(
                RuntimeEventType.TASK_COMPLETED,
                f"Task completed: {task.title}.",
                mission_id=mission.mission_id,
                workflow_id=workflow.workflow_id,
                task_id=task.task_id,
                agent_id=employee.agent_id,
                agent_name=employee.name,
            )
            self._sync_success(mission, workflow, employee)
        else:
            workflow.fail_step(
                step.step_id,
                error_message=result.message,
                retryable=result.retryable,
            )
            self.event_bus.emit(
                RuntimeEventType.TASK_FAILED,
                f"Task failed: {task.title}.",
                mission_id=mission.mission_id,
                workflow_id=workflow.workflow_id,
                task_id=task.task_id,
                agent_id=employee.agent_id,
                severity=RuntimeEventSeverity.ERROR,
            )
            self._sync_failure(mission, workflow, employee, result.message)

        if employee.current_task is not None and not employee.has_active_task:
            employee.clear_current_task()
        self.state_manager.update_employee_state(
            employee.agent_id,
            status=employee.status,
            current_task_id=None,
            current_task_title=None,
            current_mission_id=None,
            error_message=None if result.success else result.message,
        )
        return result

    def _ensure_registered(
        self, mission: MissionRecord, workflow: BaseWorkflow
    ) -> None:
        try:
            self.state_manager.get_mission_state(mission.mission_id)
        except ValidationError:
            self.state_manager.register_mission(mission)
        try:
            self.state_manager.get_workflow_state(workflow.workflow_id)
        except ValidationError:
            self.state_manager.register_workflow(workflow)

    def _start_if_needed(
        self, mission: MissionRecord, workflow: BaseWorkflow
    ) -> None:
        if workflow.status in {JobStatus.CREATED, JobStatus.PAUSED}:
            workflow.start()
        if mission.status == MissionStatus.APPROVED:
            mission.begin_planning()
        if mission.status == MissionStatus.PLANNING:
            mission.activate()
        self.state_manager.update_workflow_state(
            workflow.workflow_id,
            status=workflow.status,
            progress_percentage=workflow.progress_percentage,
            started_at=workflow.record.started_at,
        )
        self.state_manager.update_mission_state(
            mission.mission_id,
            status=mission.status,
            progress_percentage=mission.progress_percentage,
            active_workflow_id=workflow.workflow_id,
            started_at=mission.started_at,
        )

    def _resolve_employee(self, step: WorkflowStep) -> BaseEmployee | None:
        return next(
            (
                employee
                for employee in self._employees.values()
                if employee.department == step.department
                and employee.can_accept_task
            ),
            None,
        )

    @staticmethod
    def _approval_blocker(workflow: BaseWorkflow) -> WorkflowStep | None:
        completed = workflow.completed_step_ids
        return next(
            (
                step
                for step in workflow.steps
                if step.status in {JobStatus.CREATED, JobStatus.QUEUED}
                and step.requires_approval
                and not step.is_approved
                and step.dependencies_completed(completed)
            ),
            None,
        )

    def _sync_success(
        self,
        mission: MissionRecord,
        workflow: BaseWorkflow,
        employee: BaseEmployee,
    ) -> None:
        self.state_manager.update_workflow_state(
            workflow.workflow_id,
            status=workflow.status,
            progress_percentage=workflow.progress_percentage,
            current_step_id=workflow.record.current_task_id,
            completed_at=workflow.record.completed_at,
        )
        if workflow.status == JobStatus.COMPLETED:
            for objective in mission.objectives:
                if not objective.achieved:
                    objective.mark_achieved()
            if mission.status == MissionStatus.ACTIVE:
                mission.complete()
        self.state_manager.update_mission_state(
            mission.mission_id,
            status=mission.status,
            progress_percentage=mission.progress_percentage,
            completed_at=mission.completed_at,
        )

    def _sync_failure(
        self,
        mission: MissionRecord,
        workflow: BaseWorkflow,
        employee: BaseEmployee,
        error_message: str,
    ) -> None:
        self.state_manager.update_workflow_state(
            workflow.workflow_id,
            status=workflow.status,
            progress_percentage=workflow.progress_percentage,
            error_message=error_message,
        )
        if workflow.status == JobStatus.FAILED and not mission.is_terminal:
            mission.fail(error_message)
        self.state_manager.update_mission_state(
            mission.mission_id,
            status=mission.status,
            progress_percentage=mission.progress_percentage,
            error_message=error_message,
        )
