"""Normal application mission commands over the shared runtime manager."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from core import AuraBaseModel
from mission_control.models import MissionRecord, TaskRecord
from runtime_engine.runtime_manager import MissionRuntimeManager


class RunNextTaskResult(AuraBaseModel):
    """Result returned by the normal run-next command."""

    mission_id: UUID
    executed: bool
    task: TaskRecord | None = None
    detail: str = Field(min_length=1, max_length=500)


class MissionCommandService:
    """Thin command adapter with no repository or employee access."""

    def __init__(self, runtime_manager: MissionRuntimeManager) -> None:
        self._runtime_manager = runtime_manager

    @property
    def runtime_manager(self) -> MissionRuntimeManager:
        """Return the shared authoritative runtime manager."""

        return self._runtime_manager

    def submit(self, mission: MissionRecord) -> MissionRecord:
        """Submit one new canonical mission."""

        return self._runtime_manager.create_mission(mission)

    def run_next(self, mission_id: UUID) -> RunNextTaskResult:
        """Execute only the next task selected by Mission Control."""

        task = self._runtime_manager.run_next(mission_id)
        return RunNextTaskResult(
            mission_id=mission_id,
            executed=task is not None,
            task=task,
            detail=(
                "Next eligible task executed."
                if task is not None
                else "No eligible task is ready."
            ),
        )
