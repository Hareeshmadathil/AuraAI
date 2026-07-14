"""Application service for deterministic Mission Execution Engine V1."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from core.constants import ApprovalStatus, DepartmentName, TaskPriority
from core.exceptions import ValidationError
from core.models import utc_now
from mission_engine.models import (
    Mission,
    MissionArtifact,
    MissionArtifactType,
    MissionAssignee,
    MissionCapability,
    MissionExecutionStatus,
    MissionHistoryEntry,
)
from mission_engine.repository import ArtifactRegistry, MissionRepository
from mission_engine.state_machine import MissionStateMachine


class MissionManager:
    """Create, persist, transition, assign, and audit V1 missions."""

    def __init__(
        self,
        repository: MissionRepository,
        artifact_registry: ArtifactRegistry,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._repository = repository
        self._artifact_registry = artifact_registry
        self._logger = logger or logging.getLogger(__name__)

    def create_mission(
        self,
        *,
        title: str,
        objective: str,
        capability: MissionCapability,
        priority: TaskPriority = TaskPriority.NORMAL,
        assigned_departments: list[DepartmentName] | None = None,
    ) -> Mission:
        """Create and save one mission in the CREATED state."""

        mission = Mission(
            title=title,
            objective=objective,
            capability=capability,
            priority=priority,
            assigned_departments=list(dict.fromkeys(assigned_departments or [])),
        )
        mission.history.append(
            MissionHistoryEntry(
                to_status=MissionExecutionStatus.CREATED,
                note="Mission created.",
            )
        )
        self.save_mission(mission)
        self._logger.info("Mission created: %s", mission.mission_id)
        return mission.model_copy(deep=True)

    def load_mission(self, mission_id: UUID) -> Mission:
        """Load a mission or raise a stable domain validation error."""

        mission = self._repository.load(mission_id)
        if mission is None:
            raise ValidationError(
                "Mission was not found.",
                error_code="MISSION_NOT_FOUND",
                details={"mission_id": str(mission_id)},
            )
        return mission

    def save_mission(self, mission: Mission) -> None:
        """Validate and persist one mission snapshot."""

        validated = Mission.model_validate(mission)
        self._repository.save(validated)

    def update_mission_state(
        self,
        mission_id: UUID,
        target: MissionExecutionStatus,
        *,
        note: str = "",
        failure_reason: str | None = None,
    ) -> Mission:
        """Apply one valid deterministic state transition and save it."""

        mission = self.load_mission(mission_id)
        MissionStateMachine.validate_transition(mission, target)
        previous = mission.status
        if target == MissionExecutionStatus.FAILED:
            clean_reason = (failure_reason or note).strip()
            if not clean_reason:
                raise ValidationError(
                    "A failure reason is required.",
                    error_code="MISSION_FAILURE_REASON_REQUIRED",
                )
            mission.failure_reason = clean_reason
        mission.status = target
        mission.updated_at = utc_now()
        mission.history.append(
            MissionHistoryEntry(
                from_status=previous,
                to_status=target,
                note=note or failure_reason or "",
            )
        )
        self.save_mission(mission)
        self._logger.info(
            "Mission %s transitioned from %s to %s",
            mission_id,
            previous.value,
            target.value,
        )
        return mission.model_copy(deep=True)

    def assign_employee(
        self,
        mission_id: UUID,
        *,
        employee_id: UUID,
        employee_name: str,
        department: DepartmentName,
    ) -> Mission:
        """Assign one unique employee and include their department."""

        mission = self.load_mission(mission_id)
        if not any(
            assignee.employee_id == employee_id
            for assignee in mission.assigned_employees
        ):
            mission.assigned_employees.append(
                MissionAssignee(
                    employee_id=employee_id,
                    employee_name=employee_name,
                    department=department,
                )
            )
        if department not in mission.assigned_departments:
            mission.assigned_departments.append(department)
        mission.updated_at = utc_now()
        self.save_mission(mission)
        return mission.model_copy(deep=True)

    def register_artifact(
        self,
        mission_id: UUID,
        *,
        artifact_type: MissionArtifactType,
        name: str,
        summary: str = "",
        produced_by_employee_id: UUID | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> MissionArtifact:
        """Register metadata and attach it to the owning mission."""

        mission = self.load_mission(mission_id)
        if produced_by_employee_id is not None and not any(
            employee.employee_id == produced_by_employee_id
            for employee in mission.assigned_employees
        ):
            raise ValidationError(
                "Artifact producer must be assigned to the mission.",
                error_code="MISSION_ARTIFACT_PRODUCER_NOT_ASSIGNED",
            )
        artifact = MissionArtifact(
            mission_id=mission_id,
            artifact_type=artifact_type,
            name=name,
            summary=summary,
            produced_by_employee_id=produced_by_employee_id,
            metadata=dict(metadata or {}),
        )
        self._artifact_registry.register(artifact)
        mission.produced_artifacts.append(artifact)
        mission.updated_at = utc_now()
        self.save_mission(mission)
        self._logger.info(
            "Mission artifact registered: mission=%s artifact=%s type=%s",
            mission_id,
            artifact.artifact_id,
            artifact.artifact_type.value,
        )
        return artifact.model_copy(deep=True)

    def approve_founder_review(
        self,
        mission_id: UUID,
        *,
        notes: str,
    ) -> Mission:
        """Approve a mission at its explicit founder-review gate."""

        mission = self.load_mission(mission_id)
        if mission.status != MissionExecutionStatus.FOUNDER_REVIEW:
            raise ValidationError(
                "Founder approval is only valid at founder review.",
                error_code="MISSION_NOT_IN_FOUNDER_REVIEW",
            )
        clean_notes = notes.strip()
        if not clean_notes:
            raise ValidationError(
                "Founder approval notes are required.",
                error_code="FOUNDER_APPROVAL_NOTES_REQUIRED",
            )
        mission.founder_approval_state = ApprovalStatus.APPROVED
        mission.updated_at = utc_now()
        self.save_mission(mission)
        self.register_artifact(
            mission_id,
            artifact_type=MissionArtifactType.APPROVAL_NOTES,
            name="Founder approval notes",
            summary=clean_notes,
        )
        return self.load_mission(mission_id)

    def retrieve_mission_history(
        self,
        mission_id: UUID,
    ) -> tuple[MissionHistoryEntry, ...]:
        """Return a defensive, chronological mission audit history."""

        mission = self.load_mission(mission_id)
        return tuple(entry.model_copy(deep=True) for entry in mission.history)
