"""Mission Manager, artifact registry, and founder-gate tests."""

from uuid import uuid4

import pytest

from core.constants import ApprovalStatus, DepartmentName
from core.exceptions import ValidationError
from mission_engine import (
    ArtifactRegistry,
    InMemoryMissionRepository,
    MissionArtifactType,
    MissionCapability,
    MissionExecutionStatus,
    MissionManager,
)


def build_manager() -> MissionManager:
    """Create an isolated deterministic manager."""

    return MissionManager(InMemoryMissionRepository(), ArtifactRegistry())


def create_mission(manager: MissionManager):
    """Create one reusable V1 mission."""

    return manager.create_mission(
        title="Mission manager test",
        objective="Verify deterministic mission management.",
        capability=MissionCapability.CONTENT_PIPELINE,
        assigned_departments=[DepartmentName.RESEARCH],
    )


def move_to_review(manager: MissionManager, mission_id):
    """Advance through every required stage without skipping."""

    mission = manager.load_mission(mission_id)
    for status in (
        MissionExecutionStatus.PLANNING,
        MissionExecutionStatus.RESEARCH,
        MissionExecutionStatus.SEO,
        MissionExecutionStatus.SCRIPT,
        MissionExecutionStatus.FOUNDER_REVIEW,
    ):
        mission = manager.update_mission_state(mission_id, status)
    return mission


def test_manager_create_load_save_and_history_are_defensive() -> None:
    """Persist snapshots without leaking mutable repository references."""

    manager = build_manager()
    created = create_mission(manager)
    loaded = manager.load_mission(created.mission_id)
    loaded.title = "Changed only in caller memory"

    assert manager.load_mission(created.mission_id).title == created.title
    history = manager.retrieve_mission_history(created.mission_id)
    assert len(history) == 1
    assert history[0].to_status == MissionExecutionStatus.CREATED


def test_manager_assigns_each_employee_once_and_tracks_department() -> None:
    """Keep assignment metadata unique and dashboard-readable."""

    manager = build_manager()
    mission = create_mission(manager)
    employee_id = uuid4()

    for _ in range(2):
        mission = manager.assign_employee(
            mission.mission_id,
            employee_id=employee_id,
            employee_name="Atlas",
            department=DepartmentName.RESEARCH,
        )

    assert len(mission.assigned_employees) == 1
    assert mission.assigned_employees[0].employee_name == "Atlas"
    assert mission.assigned_departments == [DepartmentName.RESEARCH]


def test_artifact_registration_is_metadata_only_and_auditable() -> None:
    """Attach typed output metadata without rendering or file writes."""

    repository = InMemoryMissionRepository()
    registry = ArtifactRegistry()
    manager = MissionManager(repository, registry)
    mission = create_mission(manager)
    employee_id = uuid4()
    manager.assign_employee(
        mission.mission_id,
        employee_id=employee_id,
        employee_name="Nova",
        department=DepartmentName.RESEARCH,
    )

    artifact = manager.register_artifact(
        mission.mission_id,
        artifact_type=MissionArtifactType.RESEARCH,
        name="Niche evidence summary",
        summary="Metadata only; no source document stored.",
        produced_by_employee_id=employee_id,
        metadata={"evidence_count": 3},
    )

    stored = manager.load_mission(mission.mission_id)
    assert stored.produced_artifacts == [artifact]
    assert registry.load(artifact.artifact_id) == artifact
    assert registry.for_mission(mission.mission_id) == (artifact,)


def test_artifact_producer_must_be_assigned() -> None:
    """Reject output attribution to an employee outside the mission."""

    manager = build_manager()
    mission = create_mission(manager)

    with pytest.raises(ValidationError) as raised:
        manager.register_artifact(
            mission.mission_id,
            artifact_type=MissionArtifactType.SCRIPT,
            name="Unowned script",
            produced_by_employee_id=uuid4(),
        )

    assert raised.value.error_code == "MISSION_ARTIFACT_PRODUCER_NOT_ASSIGNED"


def test_founder_gate_blocks_then_allows_completion() -> None:
    """Require explicit reviewed approval notes before completion."""

    manager = build_manager()
    mission = create_mission(manager)
    mission = move_to_review(manager, mission.mission_id)

    with pytest.raises(ValidationError) as raised:
        manager.update_mission_state(
            mission.mission_id,
            MissionExecutionStatus.COMPLETED,
        )
    assert raised.value.error_code == "FOUNDER_APPROVAL_REQUIRED"

    mission = manager.approve_founder_review(
        mission.mission_id,
        notes="Founder reviewed and approved the metadata package.",
    )
    assert mission.founder_approval_state == ApprovalStatus.APPROVED
    assert mission.produced_artifacts[-1].artifact_type == (
        MissionArtifactType.APPROVAL_NOTES
    )

    completed = manager.update_mission_state(
        mission.mission_id,
        MissionExecutionStatus.COMPLETED,
    )
    assert completed.status == MissionExecutionStatus.COMPLETED
    assert completed.progress_percentage == 100.0
    assert len(manager.retrieve_mission_history(mission.mission_id)) == 7


def test_failure_requires_reason_and_is_terminal() -> None:
    """Record deterministic failure details and prohibit later execution."""

    manager = build_manager()
    mission = create_mission(manager)

    with pytest.raises(ValidationError):
        manager.update_mission_state(
            mission.mission_id,
            MissionExecutionStatus.FAILED,
        )

    failed = manager.update_mission_state(
        mission.mission_id,
        MissionExecutionStatus.FAILED,
        failure_reason="Required research input was unavailable.",
    )
    assert failed.failure_reason
    with pytest.raises(ValidationError):
        manager.update_mission_state(
            mission.mission_id,
            MissionExecutionStatus.PLANNING,
        )
