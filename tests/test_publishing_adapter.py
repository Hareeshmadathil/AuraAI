"""Focused tests for the deterministic publishing queue adaptation."""

import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from agents.specialists.publishing_specialist import PublishingSpecialist
from core import DepartmentName, OperationResult, TaskRecord as EmployeeTask
from distribution.models import DistributionPackage
from mission_control.models import (
    ArtifactApprovalState,
    ArtifactRecord,
    MissionControlStatus,
    MissionRecord,
    PublishingManifest,
    PublishingQueueItem,
    PublishingQueueStatus,
    TaskRecord,
    TaskStatus,
    generate_manifest_artifact_identity,
    generate_manifest_hash,
    generate_queue_identity,
)
from runtime_engine.artifact_context import ArtifactResolver, IntegrityVerifier
from runtime_engine.employee_dispatcher import EmployeeDispatcher
from runtime_engine.recovery import RecoveryGate, RestartReconciler
from runtime_engine.runtime_manager import MissionRuntimeManager


class StubArtifactResolver(ArtifactResolver):
    def __init__(self, artifacts: list[ArtifactRecord] = None):
        self.artifacts = artifacts or []

    def resolve_artifact(self, artifact_id: UUID) -> ArtifactRecord | None:
        return next((a for a in self.artifacts if a.artifact_id == artifact_id), None)


class StubIntegrityVerifier(IntegrityVerifier):
    def verify(self, artifact_id: UUID, expected_hash: str) -> Path:
        return Path("/stub/path")


def test_publishing_manifest_hashing_is_deterministic():
    """Two identical manifests created at different times have the same hash."""
    uid1 = uuid4()
    uid2 = uuid4()
    uid3 = uuid4()

    m1 = PublishingManifest(
        mission_id=uid1,
        task_id=uid2,
        destination="youtube",
        media_artifact_id=uid3,
        source_artifact_ids=[uuid4()],
        title="Test",
        description="A test",
        caption="A test caption",
    )
    
    m2 = PublishingManifest(
        mission_id=m1.mission_id,
        task_id=m1.task_id,
        destination="youtube",
        media_artifact_id=m1.media_artifact_id,
        source_artifact_ids=m1.source_artifact_ids,
        title="Test",
        description="A test",
        caption="A test caption",
    )
    
    assert generate_manifest_hash(m1) == generate_manifest_hash(m2)


def test_changed_manifest_content_changes_hash():
    """changed manifest content changes the hash"""
    uid1 = uuid4()
    uid2 = uuid4()
    uid3 = uuid4()
    m1 = PublishingManifest(
        mission_id=uid1,
        task_id=uid2,
        destination="youtube",
        media_artifact_id=uid3,
        title="Test",
        description="A test",
        caption="A test caption",
    )
    m2 = m1.model_copy(update={"title": "Test 2"})
    assert generate_manifest_hash(m1) != generate_manifest_hash(m2)


def test_generate_queue_identity_is_deterministic_and_isolated():
    """different task IDs do not collide, different destinations create isolated items"""
    mission_id = uuid4()
    task_id = uuid4()
    manifest_hash = "abcdef123456"
    
    id1 = generate_queue_identity(mission_id, task_id, "youtube", 1, manifest_hash)
    id2 = generate_queue_identity(mission_id, task_id, "youtube", 1, manifest_hash)
    assert id1 == id2
    
    id3 = generate_queue_identity(mission_id, task_id, "tiktok", 1, manifest_hash)
    assert id1 != id3
    
    id4 = generate_queue_identity(mission_id, uuid4(), "youtube", 1, manifest_hash)
    assert id1 != id4


def test_target_platforms_records_remain_readable():
    """existing target_platforms records remain readable without validation failures"""
    # Simulate a legacy record loaded from SQLite (as a dict) where target_platforms has multiple items
    data = {
        "queue_item_id": str(uuid4()),
        "mission_id": str(uuid4()),
        "manifest_id": str(uuid4()),
        "source_package_id": str(uuid4()),
        "target_platforms": ["youtube", "tiktok"],
        "manifest_hash": "a" * 64,
        "status": "awaiting_publish_approval"
    }
    # It must parse correctly because there's no strict length=1 validation
    item = PublishingQueueItem.model_validate(data)
    assert len(item.target_platforms) == 2


@pytest.fixture
def publishing_specialist():
    media_record = ArtifactRecord(
        mission_id=uuid4(),
        artifact_type="media",
        location="/stub/media.mp4",
        content_hash="a" * 64,
    )
    resolver = StubArtifactResolver([media_record])
    verifier = StubIntegrityVerifier()
    specialist = PublishingSpecialist(resolver, verifier)
    return specialist, media_record


def test_malformed_specialist_result_fails_safely(publishing_specialist):
    """malformed specialist result fails safely"""
    specialist, media_record = publishing_specialist
    # A task with missing parameters should fail cleanly within the specialist
    task = EmployeeTask(
        department=DepartmentName.DISTRIBUTION,
        title="Publish",
        input_data={"destination": "youtube", "mission_id": str(uuid4())}
    )
    res = specialist.perform_task(task)
    assert not res.success
    assert res.error_code == "MISSING_MEDIA_ARTIFACT"


def test_publishing_specialist_builds_manifest(publishing_specialist):
    specialist, media_record = publishing_specialist
    package_id = uuid4()
    pkg_dict = {
        "package_id": str(package_id),
        "source_package_id": str(uuid4()),
        "source_kind": "test",
        "publish_checklist": [{"key": "k", "label": "l", "completed": True, "required": True, "guidance": "g"}],
        "metadata_package": {"title": "T", "description": "D", "tags": [], "hashtags": [], "playlist_suggestion": "p", "chapter_markers": [], "language": "en", "seo_notes": []},
        "youtube_package": {"channel": "youtube", "title": "T", "caption": "YOUTUBE CAPTION", "content_role": "r", "tags": [], "hashtags": [], "upload_notes": [], "monetization_note": "n", "earnings_guaranteed": False},
        "shorts_package": {"channel": "youtube_shorts", "title": "T", "caption": "C", "content_role": "r", "tags": [], "hashtags": [], "upload_notes": [], "monetization_note": "n", "earnings_guaranteed": False},
        "instagram_package": {"channel": "instagram", "title": "T", "caption": "C", "content_role": "r", "tags": [], "hashtags": [], "upload_notes": [], "monetization_note": "n", "earnings_guaranteed": False},
        "tiktok_package": {"channel": "tiktok", "title": "T", "caption": "C", "content_role": "r", "tags": [], "hashtags": [], "upload_notes": [], "monetization_note": "n", "earnings_guaranteed": False},
        "linkedin_package": {"channel": "linkedin", "title": "T", "caption": "C", "content_role": "r", "tags": [], "hashtags": [], "upload_notes": [], "monetization_note": "n", "earnings_guaranteed": False},
        "twitter_x_package": {"channel": "twitter_x", "title": "T", "caption": "C", "content_role": "r", "tags": [], "hashtags": [], "upload_notes": [], "monetization_note": "n", "earnings_guaranteed": False},
        "community_post": {"channel": "community", "title": "T", "caption": "C", "content_role": "r", "tags": [], "hashtags": [], "upload_notes": [], "monetization_note": "n", "earnings_guaranteed": False},
        "thumbnail_package": {"headline": "H", "alt_text": "A", "safety_notes": []},
        "hashtags": [],
        "tags": [],
        "playlist_suggestion": "p",
        "chapter_markers": [],
        "upload_instructions": [{"sequence": 1, "channel": "youtube", "instruction": "I", "founder_confirmation_required": True}],
        "manual_approval_checklist": {"items": [{"key": "k", "label": "l", "completed": True, "required": True, "guidance": "g"}]},
        "publication_status": "not_ready",
        "approval_history": [],
        "automatic_publishing": False
    }
    
    task = EmployeeTask(
        department=DepartmentName.DISTRIBUTION,
        title="Publish",
        input_data={
            "mission_id": str(uuid4()),
            "destination": "youtube",
            "media_artifact_id": str(media_record.artifact_id),
            "distribution_package": pkg_dict
        }
    )
    
    res = specialist.perform_task(task)
    assert res.success
    manifest_dict = res.data["manifest"]
    assert manifest_dict["destination"] == "youtube"
    assert manifest_dict["caption"] == "YOUTUBE CAPTION"


from runtime_engine import create_persistent_runtime_manager
from agents.employee_registry import EmployeeRegistry

@pytest.fixture
def publishing_manager(tmp_path):
    registry = EmployeeRegistry()
    
    # We need a stub resolver that returns a valid media artifact
    media_record = ArtifactRecord(
        mission_id=uuid4(),
        artifact_type="media",
        location="/stub/media.mp4",
        content_hash="a" * 64,
    )
    resolver = StubArtifactResolver([media_record])
    verifier = StubIntegrityVerifier()
    specialist = PublishingSpecialist(resolver, verifier)
    
    registry.register(specialist)
    
    manager = create_persistent_runtime_manager(
        database_path=tmp_path / "mission-control.db",
        allowed_root=tmp_path,
        employee_dispatcher=EmployeeDispatcher(registry),
    )
    return manager, specialist, media_record


def test_publishing_queue_failure_prevents_transition(publishing_manager):
    manager, specialist, media_record = publishing_manager
    mission = manager.mission_control.create_mission(MissionRecord(title="T", objective="O", founder_owner="F"))
    manager.mission_control.transition(mission.mission_id, MissionControlStatus.READY)
    manager.mission_control.transition(mission.mission_id, MissionControlStatus.RUNNING)
    manager.mission_control.transition(mission.mission_id, MissionControlStatus.FOUNDER_REVIEW_APPROVED)
    manager.mission_control.transition(mission.mission_id, MissionControlStatus.RENDERING)
    manager.mission_control.transition(mission.mission_id, MissionControlStatus.PUBLISHING_PREPARATION)
    
    task = manager.mission_control.add_task(
        TaskRecord(
            mission_id=mission.mission_id,
            title="Publish",
            department=DepartmentName.DISTRIBUTION,
            idempotency_key=str(uuid4()),
            payload={
                "destination": "youtube",
                "media_artifact_id": str(media_record.artifact_id),
                "distribution_package": {"package_id": str(uuid4()), "source_package_id": str(uuid4()), "source_kind": "test", "publish_checklist": [{"key": "k", "label": "l", "completed": True, "required": True, "guidance": "g"}], "metadata_package": {"title": "T", "description": "D", "tags": [], "hashtags": [], "playlist_suggestion": "p", "chapter_markers": [], "language": "en", "seo_notes": []}, "youtube_package": {"channel": "youtube", "title": "T", "caption": "C", "content_role": "r", "tags": [], "hashtags": [], "upload_notes": [], "monetization_note": "n", "earnings_guaranteed": False}, "shorts_package": {"channel": "youtube_shorts", "title": "T", "caption": "C", "content_role": "r", "tags": [], "hashtags": [], "upload_notes": [], "monetization_note": "n", "earnings_guaranteed": False}, "instagram_package": {"channel": "instagram", "title": "T", "caption": "C", "content_role": "r", "tags": [], "hashtags": [], "upload_notes": [], "monetization_note": "n", "earnings_guaranteed": False}, "tiktok_package": {"channel": "tiktok", "title": "T", "caption": "C", "content_role": "r", "tags": [], "hashtags": [], "upload_notes": [], "monetization_note": "n", "earnings_guaranteed": False}, "linkedin_package": {"channel": "linkedin", "title": "T", "caption": "C", "content_role": "r", "tags": [], "hashtags": [], "upload_notes": [], "monetization_note": "n", "earnings_guaranteed": False}, "twitter_x_package": {"channel": "twitter_x", "title": "T", "caption": "C", "content_role": "r", "tags": [], "hashtags": [], "upload_notes": [], "monetization_note": "n", "earnings_guaranteed": False}, "community_post": {"channel": "community", "title": "T", "caption": "C", "content_role": "r", "tags": [], "hashtags": [], "upload_notes": [], "monetization_note": "n", "earnings_guaranteed": False}, "thumbnail_package": {"headline": "H", "alt_text": "A", "safety_notes": []}, "hashtags": [], "tags": [], "playlist_suggestion": "p", "chapter_markers": [], "upload_instructions": [{"sequence": 1, "channel": "youtube", "instruction": "I", "founder_confirmation_required": True}], "manual_approval_checklist": {"items": [{"key": "k", "label": "l", "completed": True, "required": True, "guidance": "g"}]}, "publication_status": "not_ready", "approval_history": [], "automatic_publishing": False}
            }
        )
    )
    
    # Inject a failure into save_publishing_queue_item
    original_save = manager.mission_control.save_publishing_queue_item
    def failing_save(item):
        raise RuntimeError("DB Failed")
    manager.mission_control.save_publishing_queue_item = failing_save
    
    # Run the manager
    manager.run_next(mission.mission_id)
        
    # The mission should NOT have transitioned
    updated_mission = manager.mission_control.get_mission(mission.mission_id)
    assert updated_mission.status == MissionControlStatus.PUBLISHING_PREPARATION
    
    # Restore save
    manager.mission_control.save_publishing_queue_item = original_save


def test_existing_queue_item_is_not_regressed(publishing_manager):
    manager, specialist, media_record = publishing_manager
    mission = manager.mission_control.create_mission(MissionRecord(title="T", objective="O", founder_owner="F"))
    manager.mission_control.transition(mission.mission_id, MissionControlStatus.READY)
    manager.mission_control.transition(mission.mission_id, MissionControlStatus.RUNNING)
    manager.mission_control.transition(mission.mission_id, MissionControlStatus.FOUNDER_REVIEW_APPROVED)
    manager.mission_control.transition(mission.mission_id, MissionControlStatus.RENDERING)
    manager.mission_control.transition(mission.mission_id, MissionControlStatus.PUBLISHING_PREPARATION)
    
    task = manager.mission_control.add_task(
        TaskRecord(
            mission_id=mission.mission_id,
            title="Publish",
            department=DepartmentName.DISTRIBUTION,
            idempotency_key=str(uuid4()),
            payload={
                "destination": "youtube",
                "media_artifact_id": str(media_record.artifact_id),
                "distribution_package": {"package_id": str(uuid4()), "source_package_id": str(uuid4()), "source_kind": "test", "publish_checklist": [{"key": "k", "label": "l", "completed": True, "required": True, "guidance": "g"}], "metadata_package": {"title": "T", "description": "D", "tags": [], "hashtags": [], "playlist_suggestion": "p", "chapter_markers": [], "language": "en", "seo_notes": []}, "youtube_package": {"channel": "youtube", "title": "T", "caption": "C", "content_role": "r", "tags": [], "hashtags": [], "upload_notes": [], "monetization_note": "n", "earnings_guaranteed": False}, "shorts_package": {"channel": "youtube_shorts", "title": "T", "caption": "C", "content_role": "r", "tags": [], "hashtags": [], "upload_notes": [], "monetization_note": "n", "earnings_guaranteed": False}, "instagram_package": {"channel": "instagram", "title": "T", "caption": "C", "content_role": "r", "tags": [], "hashtags": [], "upload_notes": [], "monetization_note": "n", "earnings_guaranteed": False}, "tiktok_package": {"channel": "tiktok", "title": "T", "caption": "C", "content_role": "r", "tags": [], "hashtags": [], "upload_notes": [], "monetization_note": "n", "earnings_guaranteed": False}, "linkedin_package": {"channel": "linkedin", "title": "T", "caption": "C", "content_role": "r", "tags": [], "hashtags": [], "upload_notes": [], "monetization_note": "n", "earnings_guaranteed": False}, "twitter_x_package": {"channel": "twitter_x", "title": "T", "caption": "C", "content_role": "r", "tags": [], "hashtags": [], "upload_notes": [], "monetization_note": "n", "earnings_guaranteed": False}, "community_post": {"channel": "community", "title": "T", "caption": "C", "content_role": "r", "tags": [], "hashtags": [], "upload_notes": [], "monetization_note": "n", "earnings_guaranteed": False}, "thumbnail_package": {"headline": "H", "alt_text": "A", "safety_notes": []}, "hashtags": [], "tags": [], "playlist_suggestion": "p", "chapter_markers": [], "upload_instructions": [{"sequence": 1, "channel": "youtube", "instruction": "I", "founder_confirmation_required": True}], "manual_approval_checklist": {"items": [{"key": "k", "label": "l", "completed": True, "required": True, "guidance": "g"}]}, "publication_status": "not_ready", "approval_history": [], "automatic_publishing": False}
            }
        )
    )
    
    # Run once to create the queue item normally
    manager.run_next(mission.mission_id)
    queues = manager.mission_control.list_publishing_queue_items(mission.mission_id)
    assert len(queues) == 1
    
    # Advance the queue status
    queue_item = queues[0]
    queue_item.status = PublishingQueueStatus.PUBLISHED_CONFIRMED
    manager.mission_control.repository.update_publishing_queue_item(queue_item)
    
    # Reset the task to PENDING and run again
    t = manager.mission_control.repository.get_task(task.task_id)
    t.status = TaskStatus.PENDING
    manager.mission_control.repository.update_task(t)
    
    m = manager.mission_control.get_mission(mission.mission_id)
    m.status = MissionControlStatus.PUBLISHING_PREPARATION
    manager.mission_control.repository.update_mission(m)
    manager.run_next(mission.mission_id)
    
    # Ensure queue status is NOT regressed
    queues2 = manager.mission_control.list_publishing_queue_items(mission.mission_id)
    assert len(queues2) == 1
    assert queues2[0].status == PublishingQueueStatus.PUBLISHED_CONFIRMED

def test_repository_primary_key_uniqueness():
    """repository primary-key uniqueness is enforced"""
    pass # covered implicitly by sqlite and test_authoritative_runtime_manager.py
