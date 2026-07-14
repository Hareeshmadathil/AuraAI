"""Mission metadata registry and typed artifact versioning tests."""

from mission_engine import (
    ArtifactRegistry,
    InMemoryMissionRepository,
    MissionArtifactStatus,
    MissionArtifactType,
    MissionCapability,
    MissionManager,
)


def test_mission_artifacts_receive_deterministic_versions_and_hashes() -> None:
    manager = MissionManager(
        InMemoryMissionRepository(), ArtifactRegistry(), audit_actions=True
    )
    mission = manager.create_mission(
        title="Version artifacts",
        objective="Preserve script revisions",
        capability=MissionCapability.SCRIPT,
    )
    first = manager.register_artifact(
        mission.mission_id,
        artifact_type=MissionArtifactType.SCRIPT,
        name="ScriptArtifact",
        summary="Original",
    )
    second = manager.register_artifact(
        mission.mission_id,
        artifact_type=MissionArtifactType.SCRIPT,
        name="ScriptArtifact",
        summary="Revision",
        parent_artifact_id=first.artifact_id,
    )
    stored = manager.load_mission(mission.mission_id).produced_artifacts

    assert [item.version_number for item in stored] == [1, 2]
    assert stored[0].status == MissionArtifactStatus.SUPERSEDED
    assert stored[1].status == MissionArtifactStatus.CURRENT
    assert second.parent_artifact_id == first.artifact_id
    assert len(second.content_hash) == 64
    assert any(entry.action == "artifact_registered" for entry in manager.retrieve_mission_history(mission.mission_id))
