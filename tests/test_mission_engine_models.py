"""Mission Execution Engine V1 domain and state-machine tests."""

from uuid import uuid4

import pytest
from pydantic import ValidationError as PydanticValidationError

from core.constants import ApprovalStatus, DepartmentName, TaskPriority
from core.exceptions import ValidationError
from mission_engine import (
    Mission,
    MissionArtifact,
    MissionArtifactType,
    MissionAssignee,
    MissionCapability,
    MissionExecutionStatus,
    MissionStateMachine,
)


def build_mission() -> Mission:
    """Create one valid mission at its initial state."""

    return Mission(
        title="Produce one reviewed educational content package",
        objective="Create a safe package through the deterministic pipeline.",
        capability=MissionCapability.CONTENT_PIPELINE,
        priority=TaskPriority.HIGH,
    )


def test_mission_creation_has_typed_identity_and_defaults() -> None:
    """Create unique strongly typed mission records."""

    first = build_mission()
    second = build_mission()

    assert first.mission_id != second.mission_id
    assert first.status == MissionExecutionStatus.CREATED
    assert first.founder_approval_state == ApprovalStatus.PENDING
    assert first.created_at.tzinfo is not None
    assert first.updated_at.tzinfo is not None
    assert first.progress_percentage == 0.0


def test_state_machine_accepts_only_the_deterministic_sequence() -> None:
    """Allow the documented path and reject skipped or terminal transitions."""

    mission = build_mission()
    MissionStateMachine.validate_transition(
        mission,
        MissionExecutionStatus.PLANNING,
    )

    with pytest.raises(ValidationError) as raised:
        MissionStateMachine.validate_transition(
            mission,
            MissionExecutionStatus.SCRIPT,
        )

    assert raised.value.error_code == "INVALID_MISSION_TRANSITION"
    assert MissionStateMachine.allowed_targets(
        MissionExecutionStatus.COMPLETED
    ) == frozenset()


def test_completed_model_requires_founder_approval() -> None:
    """Prevent invalid completed data from entering through serialization."""

    with pytest.raises(PydanticValidationError):
        Mission(
            title="Invalid completion",
            objective="Attempt to bypass founder review.",
            capability=MissionCapability.SCRIPT,
            status=MissionExecutionStatus.COMPLETED,
        )


def test_mission_serialization_preserves_assignments_and_artifacts() -> None:
    """Round-trip the complete typed domain record as JSON."""

    mission = build_mission()
    employee_id = uuid4()
    mission.assigned_departments.append(DepartmentName.RESEARCH)
    mission.assigned_employees.append(
        MissionAssignee(
            employee_id=employee_id,
            employee_name="Atlas",
            department=DepartmentName.RESEARCH,
        )
    )
    mission.produced_artifacts.append(
        MissionArtifact(
            mission_id=mission.mission_id,
            artifact_type=MissionArtifactType.RESEARCH,
            name="Research brief",
            produced_by_employee_id=employee_id,
        )
    )

    restored = Mission.model_validate_json(mission.model_dump_json())

    assert restored == mission
    assert restored.assigned_employees[0].employee_id == employee_id
    assert restored.produced_artifacts[0].artifact_type == (
        MissionArtifactType.RESEARCH
    )
