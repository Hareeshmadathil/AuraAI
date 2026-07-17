"""Authoritative runtime facade backed exclusively by Mission Control."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from mission_control.models import TaskRecord
from mission_control.repository import SQLiteMissionControlRepository
from mission_control.service import MissionControlService
from runtime_engine.employee_dispatcher import EmployeeDispatcher


class MissionRuntimeManager:
    """Run canonical tasks without maintaining a second mission state store."""

    def __init__(
        self,
        mission_control: MissionControlService,
        employee_dispatcher: EmployeeDispatcher,
    ) -> None:
        self.mission_control = mission_control
        self.employee_dispatcher = employee_dispatcher

    def run_next(self, mission_id: UUID) -> TaskRecord | None:
        """Run the next authoritative task, or return ``None`` when none is ready."""

        actions = self.mission_control.next_actions(mission_id)
        if not actions:
            return None
        task = actions[0]
        command = self.mission_control.dispatch(task.task_id)
        result = self.employee_dispatcher.dispatch(command)
        return self.mission_control.accept_result(result)

    def recover_interrupted(self) -> list[TaskRecord]:
        """Recover tasks left running by an interrupted process."""

        return self.mission_control.recover_interrupted()


def create_persistent_runtime_manager(
    *,
    database_path: Path,
    allowed_root: Path,
    employee_dispatcher: EmployeeDispatcher,
) -> MissionRuntimeManager:
    """Compose the runtime with the free, durable SQLite state backend."""

    repository = SQLiteMissionControlRepository(
        database_path,
        allowed_root=allowed_root,
    )
    return MissionRuntimeManager(
        MissionControlService(repository),
        employee_dispatcher,
    )
