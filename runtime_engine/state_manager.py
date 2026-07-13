"""Explicit in-memory projections for the AuraAI runtime engine."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from core import (
    AgentIdentity,
    AgentStatus,
    DecisionOutcome,
    DecisionRecord,
    JobStatus,
    MissionRecord,
    MissionStatus,
    StorageError,
    ValidationError,
    WorkflowRecord,
    utc_now,
)
from runtime_engine.event_bus import RuntimeEventBus
from runtime_engine.models import (
    RuntimeEmployeeState,
    RuntimeEventType,
    RuntimeHealthComponent,
    RuntimeMissionState,
    RuntimeMode,
    RuntimeProductionState,
    RuntimeSnapshot,
    RuntimeStatistics,
    RuntimeWorkflowState,
)


class RuntimeStateManager:
    def __init__(self, event_bus: RuntimeEventBus) -> None:
        self.event_bus = event_bus
        self._mode = RuntimeMode.STOPPED
        self._employees: dict[UUID, RuntimeEmployeeState] = {}
        self._missions: dict[UUID, RuntimeMissionState] = {}
        self._workflows: dict[UUID, RuntimeWorkflowState] = {}
        self._decisions: dict[UUID, DecisionRecord] = {}
        self._health: dict[str, RuntimeHealthComponent] = {
            "runtime": RuntimeHealthComponent(status="operational")
        }
        self._production_packages: dict[UUID, RuntimeProductionState] = {}

    @property
    def mode(self) -> RuntimeMode:
        return self._mode

    def start_runtime(self) -> None:
        if self._mode not in {RuntimeMode.STOPPED, RuntimeMode.DEGRADED}:
            raise ValidationError("Runtime cannot start from its current mode.")
        self._mode = RuntimeMode.RUNNING
        self.event_bus.emit(RuntimeEventType.RUNTIME_STARTED, "Runtime started.")

    def stop_runtime(self) -> None:
        if self._mode == RuntimeMode.STOPPED:
            raise ValidationError("Runtime is already stopped.")
        self._mode = RuntimeMode.STOPPED
        self.event_bus.emit(RuntimeEventType.RUNTIME_STOPPED, "Runtime stopped.")

    def pause_runtime(self) -> None:
        if self._mode != RuntimeMode.RUNNING:
            raise ValidationError("Only a running runtime can be paused.")
        self._mode = RuntimeMode.PAUSED
        self.event_bus.emit(RuntimeEventType.WARNING, "Runtime paused.")

    def resume_runtime(self) -> None:
        if self._mode != RuntimeMode.PAUSED:
            raise ValidationError("Only a paused runtime can be resumed.")
        self._mode = RuntimeMode.RUNNING
        self.event_bus.emit(RuntimeEventType.RUNTIME_STARTED, "Runtime resumed.")

    def register_employee(
        self, employee: Any, *, replace: bool = False
    ) -> RuntimeEmployeeState:
        identity = AgentIdentity.model_validate(getattr(employee, "identity", employee))
        if identity.agent_id in self._employees and not replace:
            raise StorageError("Employee is already registered.")
        current_task = getattr(employee, "current_task", None)
        state = RuntimeEmployeeState(
            agent_id=identity.agent_id,
            name=identity.name,
            job_title=identity.job_title,
            department=identity.department,
            status=identity.status,
            current_task_id=getattr(current_task, "task_id", None),
            current_task_title=getattr(current_task, "title", None),
        )
        self._employees[identity.agent_id] = state
        return state

    def unregister_employee(self, agent_id: UUID) -> RuntimeEmployeeState:
        return self._pop(self._employees, agent_id, "Employee")

    def update_employee_state(
        self, agent_id: UUID, **changes: Any
    ) -> RuntimeEmployeeState:
        state = self.get_employee_state(agent_id)
        updated = state.model_copy(update={**changes, "last_event_at": utc_now()})
        updated = RuntimeEmployeeState.model_validate(updated)
        self._employees[agent_id] = updated
        self.event_bus.emit(
            RuntimeEventType.EMPLOYEE_STATUS_CHANGED,
            f"Employee state updated: {updated.name}.",
            agent_id=agent_id,
            agent_name=updated.name,
            department=updated.department,
        )
        return updated

    def get_employee_state(self, agent_id: UUID) -> RuntimeEmployeeState:
        return self._get(self._employees, agent_id, "Employee")

    def list_employee_states(self) -> tuple[RuntimeEmployeeState, ...]:
        return tuple(self._employees.values())

    def register_mission(
        self, mission: MissionRecord, *, replace: bool = False
    ) -> RuntimeMissionState:
        if mission.mission_id in self._missions and not replace:
            raise StorageError("Mission is already registered.")
        state = RuntimeMissionState(
            mission_id=mission.mission_id,
            title=mission.title,
            status=mission.status,
            progress_percentage=mission.progress_percentage,
            started_at=mission.started_at,
            completed_at=mission.completed_at,
            error_message=mission.failure_reason,
        )
        self._missions[mission.mission_id] = state
        self.event_bus.emit(
            RuntimeEventType.MISSION_REGISTERED,
            f"Mission registered: {mission.title}.",
            mission_id=mission.mission_id,
        )
        return state

    def update_mission_state(
        self, mission_id: UUID, **changes: Any
    ) -> RuntimeMissionState:
        state = self.get_mission_state(mission_id)
        updated = RuntimeMissionState.model_validate(
            state.model_copy(update=changes)
        )
        self._missions[mission_id] = updated
        event_type = self._mission_event(updated.status)
        self.event_bus.emit(
            event_type,
            f"Mission state updated: {updated.title}.",
            mission_id=mission_id,
        )
        return updated

    def get_mission_state(self, mission_id: UUID) -> RuntimeMissionState:
        return self._get(self._missions, mission_id, "Mission")

    def list_mission_states(self) -> tuple[RuntimeMissionState, ...]:
        return tuple(self._missions.values())

    def register_workflow(
        self, workflow: Any, *, replace: bool = False
    ) -> RuntimeWorkflowState:
        record = WorkflowRecord.model_validate(getattr(workflow, "record", workflow))
        if record.workflow_id in self._workflows and not replace:
            raise StorageError("Workflow is already registered.")
        state = RuntimeWorkflowState(
            workflow_id=record.workflow_id,
            mission_id=self._workflow_mission_id(workflow, record),
            name=record.name,
            status=record.status,
            progress_percentage=float(
                getattr(workflow, "progress_percentage", 100.0 if record.status == JobStatus.COMPLETED else 0.0)
            ),
            current_step_id=record.current_task_id,
            started_at=record.started_at,
            completed_at=record.completed_at,
            error_message=record.error_message,
        )
        self._workflows[record.workflow_id] = state
        self.event_bus.emit(
            RuntimeEventType.WORKFLOW_REGISTERED,
            f"Workflow registered: {record.name}.",
            workflow_id=record.workflow_id,
            mission_id=state.mission_id,
        )
        return state

    def update_workflow_state(
        self, workflow_id: UUID, **changes: Any
    ) -> RuntimeWorkflowState:
        state = self.get_workflow_state(workflow_id)
        updated = RuntimeWorkflowState.model_validate(
            state.model_copy(update=changes)
        )
        self._workflows[workflow_id] = updated
        self.event_bus.emit(
            self._workflow_event(updated.status),
            f"Workflow state updated: {updated.name}.",
            workflow_id=workflow_id,
            mission_id=updated.mission_id,
        )
        return updated

    def get_workflow_state(self, workflow_id: UUID) -> RuntimeWorkflowState:
        return self._get(self._workflows, workflow_id, "Workflow")

    def list_workflow_states(self) -> tuple[RuntimeWorkflowState, ...]:
        return tuple(self._workflows.values())

    def register_decision(
        self, decision: DecisionRecord, *, replace: bool = False
    ) -> DecisionRecord:
        if decision.decision_id in self._decisions and not replace:
            raise StorageError("Decision is already registered.")
        self._decisions[decision.decision_id] = decision
        self.event_bus.emit(
            RuntimeEventType.DECISION_RECORDED,
            f"Decision recorded: {decision.title}.",
            mission_id=decision.mission_id,
        )
        return decision

    def list_decisions(self) -> tuple[DecisionRecord, ...]:
        return tuple(self._decisions.values())

    def set_health_component(
        self, name: str, status: str, message: str | None = None
    ) -> None:
        if not name.strip() or not status.strip():
            raise ValidationError("Health component name and status are required.")
        self._health[name] = RuntimeHealthComponent(
            status=status,
            message=message,
        )

    def register_production_package(
        self,
        package: Any,
        *,
        replace: bool = False,
    ) -> RuntimeProductionState:
        """Register a production package without coupling runtime to its model."""

        package_id = package.package_id
        if package_id in self._production_packages and not replace:
            raise StorageError("Production package is already registered.")
        report = getattr(package, "quality_report", None)
        state = RuntimeProductionState(
            package_id=package_id,
            topic=package.input.topic,
            current_stage=package.current_stage.value,
            approval_status=package.approval_status.value,
            quality_score=(report.score_percentage if report is not None else None),
            sample_data=package.input.sample_data,
            media_rendered=False,
        )
        self._production_packages[package_id] = state
        return state

    def list_production_states(self) -> tuple[RuntimeProductionState, ...]:
        """Return registered production package projections."""

        return tuple(self._production_packages.values())

    def build_statistics(self) -> RuntimeStatistics:
        mission_states = tuple(self._missions.values())
        workflow_states = tuple(self._workflows.values())
        employee_states = tuple(self._employees.values())
        return RuntimeStatistics(
            registered_missions=len(mission_states),
            active_missions=sum(m.status in {MissionStatus.PLANNING, MissionStatus.ACTIVE, MissionStatus.PAUSED} for m in mission_states),
            completed_missions=sum(m.status == MissionStatus.COMPLETED for m in mission_states),
            failed_missions=sum(m.status == MissionStatus.FAILED for m in mission_states),
            registered_workflows=len(workflow_states),
            active_workflows=sum(w.status == JobStatus.RUNNING for w in workflow_states),
            employees_working=sum(e.status == AgentStatus.WORKING for e in employee_states),
            employees_idle=sum(e.status == AgentStatus.IDLE for e in employee_states),
            pending_decisions=sum(d.outcome == DecisionOutcome.PENDING for d in self._decisions.values()),
            total_events=self.event_bus.count(),
            production_packages=len(self._production_packages),
        )

    def snapshot(self, recent_event_limit: int = 50) -> RuntimeSnapshot:
        return RuntimeSnapshot(
            mode=self._mode,
            statistics=self.build_statistics(),
            employees=list(self._employees.values()),
            missions=list(self._missions.values()),
            workflows=list(self._workflows.values()),
            decisions=list(self._decisions.values()),
            recent_events=list(self.event_bus.recent(recent_event_limit)),
            system_health=dict(self._health),
            production_packages=list(self._production_packages.values()),
        )

    @staticmethod
    def _workflow_mission_id(workflow: Any, record: WorkflowRecord) -> UUID | None:
        mission_id = getattr(workflow, "mission_id", None)
        if mission_id is not None:
            return mission_id
        raw = record.context.get("mission_id")
        return UUID(raw) if raw else None

    @staticmethod
    def _mission_event(status: MissionStatus) -> RuntimeEventType:
        return {
            MissionStatus.ACTIVE: RuntimeEventType.MISSION_STARTED,
            MissionStatus.PAUSED: RuntimeEventType.MISSION_PAUSED,
            MissionStatus.COMPLETED: RuntimeEventType.MISSION_COMPLETED,
            MissionStatus.FAILED: RuntimeEventType.MISSION_FAILED,
        }.get(status, RuntimeEventType.MISSION_RESUMED)

    @staticmethod
    def _workflow_event(status: JobStatus) -> RuntimeEventType:
        return {
            JobStatus.RUNNING: RuntimeEventType.WORKFLOW_STARTED,
            JobStatus.COMPLETED: RuntimeEventType.WORKFLOW_COMPLETED,
            JobStatus.FAILED: RuntimeEventType.WORKFLOW_FAILED,
        }.get(status, RuntimeEventType.WORKFLOW_REGISTERED)

    @staticmethod
    def _get(mapping: dict[UUID, Any], identifier: UUID, label: str) -> Any:
        try:
            return mapping[identifier]
        except KeyError as error:
            raise ValidationError(f"{label} was not found.") from error

    @staticmethod
    def _pop(mapping: dict[UUID, Any], identifier: UUID, label: str) -> Any:
        try:
            return mapping.pop(identifier)
        except KeyError as error:
            raise ValidationError(f"{label} was not found.") from error
