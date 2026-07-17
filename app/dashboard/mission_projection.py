"""Read-only dashboard projection over authoritative Mission Control state."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.dashboard.models import MissionArtifactSummary, MissionStatusSummary
from mission_control.models import ApprovalState, TaskStatus

if TYPE_CHECKING:
    from mission_control.service import MissionControlService


class MissionControlDashboardReader:
    """Project canonical mission records without owning or mutating state."""

    def __init__(self, mission_control: MissionControlService) -> None:
        self._mission_control = mission_control

    @property
    def mission_control(self) -> MissionControlService:
        """Return the shared authority used by this reader."""

        return self._mission_control

    def list_missions(self) -> list[MissionStatusSummary]:
        """Build a fresh dashboard view from current Mission Control records."""

        return [
            self._summarize(mission)
            for mission in self._mission_control.list_missions()
        ]

    def _summarize(self, mission) -> MissionStatusSummary:
        tasks = self._mission_control.list_tasks(mission.mission_id)
        artifacts = self._mission_control.list_artifacts(mission.mission_id)
        approvals = self._mission_control.list_approvals(mission.mission_id)
        completed_tasks = sum(
            task.status == TaskStatus.COMPLETED for task in tasks
        )
        progress = (
            completed_tasks / len(tasks) * 100.0
            if tasks
            else 0.0
        )
        latest_approval = max(
            approvals,
            key=lambda approval: approval.issued_at,
            default=None,
        )
        lead_department = (
            mission.required_departments[0]
            if mission.required_departments
            else None
        )
        return MissionStatusSummary(
            mission_id=mission.mission_id,
            title=mission.title,
            description=mission.objective,
            objective=mission.objective,
            status=mission.status,
            priority=mission.priority,
            lead_department=lead_department,
            progress_percentage=progress,
            founder_approval_state=(
                latest_approval.state.value
                if latest_approval is not None
                else ApprovalState.PENDING.value
                if mission.required_approvals
                else ""
            ),
            assigned_departments=mission.required_departments,
            assigned_employees=[
                str(task.assigned_agent_id)
                for task in tasks
                if task.assigned_agent_id is not None
            ],
            generated_artifacts=[
                MissionArtifactSummary(
                    artifact_id=artifact.artifact_id,
                    artifact_type=artifact.artifact_type,
                    name=artifact.location,
                    summary=str(artifact.metadata.get("summary", "")),
                )
                for artifact in artifacts
            ],
        )
