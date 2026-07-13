"""High-level deterministic coordination for AuraAI runtime operations."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from agents.base_employee import BaseEmployee
from agents.executive import AuraCOO
from core import (
    MissionRecord,
    MissionStatus,
    OperationResult,
    StorageError,
    ValidationError,
)
from runtime_engine.event_bus import RuntimeEventBus
from runtime_engine.mission_runner import MissionRunner
from runtime_engine.models import RuntimeEventType, RuntimeMode, RuntimeSnapshot
from runtime_engine.state_manager import RuntimeStateManager
from workflows.base_workflow import BaseWorkflow


class RuntimeOrchestrator:
    def __init__(
        self,
        event_bus: RuntimeEventBus,
        state_manager: RuntimeStateManager,
        coo: AuraCOO,
        mission_runner: MissionRunner,
        employees: Iterable[BaseEmployee] = (),
    ) -> None:
        self.event_bus = event_bus
        self.state_manager = state_manager
        self.coo = coo
        self.mission_runner = mission_runner
        self._employees: dict[UUID, BaseEmployee] = {}
        self._missions: dict[UUID, MissionRecord] = {}
        self._workflows: dict[UUID, BaseWorkflow] = {}
        for employee in employees:
            self.register_employee(employee)

    def register_employee(self, employee: BaseEmployee) -> None:
        if employee.agent_id in self._employees:
            raise StorageError("Orchestrator employee is already registered.")
        self._employees[employee.agent_id] = employee
        self.mission_runner.register_employee(employee)

    def register_employees(self, employees: Iterable[BaseEmployee]) -> None:
        for employee in employees:
            self.register_employee(employee)

    def list_registered_employees(self) -> tuple[BaseEmployee, ...]:
        return tuple(self._employees.values())

    def register_mission(self, mission: MissionRecord) -> None:
        if mission.mission_id in self._missions:
            raise StorageError("Mission is already registered.")
        self._missions[mission.mission_id] = mission
        self.state_manager.register_mission(mission)

    def start_mission(self, mission: MissionRecord) -> BaseWorkflow:
        self._require_running()
        if mission.is_terminal or not mission.is_approved:
            raise ValidationError(
                "Only approved, non-terminal missions may start."
            )
        if mission.mission_id in self._missions:
            raise StorageError("Mission has already been started.")
        workflow = self.create_workflow_for_mission(mission)
        self._missions[mission.mission_id] = mission
        self.state_manager.register_mission(mission)
        self.state_manager.update_mission_state(
            mission.mission_id,
            status=mission.status,
            active_workflow_id=workflow.workflow_id,
        )
        self.event_bus.emit(
            RuntimeEventType.MISSION_STARTED,
            f"Mission started: {mission.title}.",
            mission_id=mission.mission_id,
            workflow_id=workflow.workflow_id,
        )
        return workflow

    def pause_mission(self, mission_id: UUID) -> None:
        mission = self._get_mission(mission_id)
        if mission.status == MissionStatus.ACTIVE:
            mission.pause()
        self.state_manager.update_mission_state(
            mission_id,
            status=MissionStatus.PAUSED,
            paused_at=mission.updated_at,
        )

    def resume_mission(self, mission_id: UUID) -> None:
        mission = self._get_mission(mission_id)
        if mission.status != MissionStatus.PAUSED:
            raise ValidationError("Only paused missions may resume.")
        mission.activate()
        self.state_manager.update_mission_state(
            mission_id,
            status=mission.status,
            paused_at=None,
        )

    def stop_mission(self, mission_id: UUID) -> None:
        mission = self._get_mission(mission_id)
        mission.cancel("Stopped by runtime orchestrator.")
        self.state_manager.update_mission_state(
            mission_id,
            status=mission.status,
            completed_at=mission.completed_at,
        )

    def get_mission_state(self, mission_id: UUID):
        return self.state_manager.get_mission_state(mission_id)

    def create_workflow_for_mission(
        self, mission: MissionRecord
    ) -> BaseWorkflow:
        workflow = self.coo.coordinate_mission(mission)
        self._workflows[workflow.workflow_id] = workflow
        self.state_manager.register_workflow(workflow)
        return workflow

    def run_mission(self, mission: MissionRecord) -> OperationResult:
        if mission.mission_id not in self._missions:
            workflow = self.start_mission(mission)
        else:
            workflow = self._workflow_for_mission(mission.mission_id)
        return self.mission_runner.run_workflow(mission, workflow)

    def run_next_mission_step(self, mission_id: UUID) -> OperationResult:
        self._require_running()
        mission = self._get_mission(mission_id)
        workflow = self._workflow_for_mission(mission_id)
        return self.mission_runner.run_next_step(mission, workflow)

    def get_workflow_state(self, workflow_id: UUID):
        return self.state_manager.get_workflow_state(workflow_id)

    def start(self) -> None:
        self.state_manager.start_runtime()
        self.mission_runner.resume()

    def stop(self) -> None:
        self.mission_runner.stop()
        self.state_manager.stop_runtime()

    def pause(self) -> None:
        self.mission_runner.pause()
        self.state_manager.pause_runtime()

    def resume(self) -> None:
        self.state_manager.resume_runtime()
        self.mission_runner.resume()

    def snapshot(self) -> RuntimeSnapshot:
        return self.state_manager.snapshot()

    def _require_running(self) -> None:
        if self.state_manager.mode != RuntimeMode.RUNNING:
            raise ValidationError("Runtime must be running to execute work.")

    def _get_mission(self, mission_id: UUID) -> MissionRecord:
        try:
            return self._missions[mission_id]
        except KeyError as error:
            raise ValidationError("Mission was not found.") from error

    def _workflow_for_mission(self, mission_id: UUID) -> BaseWorkflow:
        for workflow in self._workflows.values():
            if getattr(workflow, "mission_id", None) == mission_id:
                return workflow
        raise ValidationError("Mission workflow was not found.")
