"""Phase 3 Milestone 5: Manual Publish Confirmation Tests."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from uuid import uuid4
from datetime import timedelta

import pytest

from core import utc_now
from mission_control.models import (
    ApprovalRequest,
    RiskLevel,
    PublishingQueueItem,
    PublishingQueueStatus,
    ConflictingDecisionError,
    ItemNotFoundError,
    StaleContentError,
    MismatchError,
    MalformedCommandError,
    PublicationRecord,
    MissionRecord,
    ApprovalState,
)
from mission_control.repository import SQLiteMissionControlRepository
from mission_control.service import MissionControlService

# Setup helpers
@pytest.fixture
def repo(tmp_path: Path):
    return SQLiteMissionControlRepository(tmp_path / "mission_control.db", allowed_root=tmp_path)

@pytest.fixture
def service(repo):
    return MissionControlService(repo)

@pytest.fixture
def setup_mission(service):
    m = MissionRecord(title="test mission", founder_goal="goal", objective="goal", founder_owner="test", required_publish_destinations=["youtube"], publishing_generation=1)
    mission = service.create_mission(m)
    queue_item = PublishingQueueItem(
        mission_id=mission.mission_id,
        manifest_id=uuid4(),
        source_package_id=uuid4(),
        target_platforms=["youtube"],
        destination="youtube",
        generation=mission.publishing_generation,
        manifest_hash="a" * 64,
    )
    service.repository.save_publishing_queue_item(queue_item)
    
    approval = ApprovalRequest(
        mission_id=mission.mission_id,
        subject_type="publishing_queue_item",
        subject_id=queue_item.queue_item_id,
        requested_action="approve_publishing",
        risk=RiskLevel.CONSEQUENTIAL,
        content_hash=queue_item.manifest_hash,
        expires_at=utc_now() + timedelta(hours=1),
    )
    service.repository.save_approval(approval)
    queue_item.approval_id = approval.approval_id
    service.repository.update_publishing_queue_item(queue_item)
    
    # Approve
    service.apply_publish_decision(
        mission_id=mission.mission_id,
        queue_item_id=queue_item.queue_item_id,
        approval_id=approval.approval_id,
        content_hash=queue_item.manifest_hash,
        decision=ApprovalState.APPROVED,
        reason="looks good",
        actor="founder",
    )
    
    q = service.repository.get_publishing_queue_item(queue_item.queue_item_id)
    assert q.status == PublishingQueueStatus.READY_FOR_MANUAL_PUBLISH
    
    return mission, q, approval

def test_first_successful_confirmation(service, setup_mission):
    mission, queue_item, _ = setup_mission
    q, pub = service.confirm_manual_publication(
        mission_id=mission.mission_id,
        queue_item_id=queue_item.queue_item_id,
        content_hash=queue_item.manifest_hash,
        external_url="https://youtube.com/v123",
        external_post_id="post123",
        confirmation_note="done",
        actor="founder",
    )
    assert q.status == PublishingQueueStatus.PUBLISHED_CONFIRMED
    assert pub.external_url == "https://youtube.com/v123"
    assert pub.external_post_id == "post123"
    assert pub.confirmation_note == "done"
    assert pub.published_by_actor == "founder"
    assert pub.queue_item_id == queue_item.queue_item_id
    
    # Check events
    events = service.repository.list_events(mission.mission_id)
    pub_events = [e for e in events if e.event_type == "publication.confirmed"]
    assert len(pub_events) == 1
    assert pub_events[0].payload["external_url"] == "https://youtube.com/v123"
    assert pub_events[0].payload["confirmation_note"] == "done"

def test_sequential_identical_retry(service, setup_mission):
    mission, queue_item, _ = setup_mission
    args = dict(
        mission_id=mission.mission_id, queue_item_id=queue_item.queue_item_id,
        content_hash=queue_item.manifest_hash, external_url="https://x.com",
        external_post_id=None, confirmation_note=None, actor="founder",
    )
    q1, pub1 = service.confirm_manual_publication(**args)
    q2, pub2 = service.confirm_manual_publication(**args)
    assert q1.status == q2.status == PublishingQueueStatus.PUBLISHED_CONFIRMED
    assert pub1.publication_id == pub2.publication_id
    
    # Check no duplicate event
    events = [e for e in service.repository.list_events(mission.mission_id) if e.event_type == "publication.confirmed"]
    assert len(events) == 1

def test_different_actor_identical_retry(service, setup_mission):
    mission, queue_item, _ = setup_mission
    service.confirm_manual_publication(
        mission_id=mission.mission_id, queue_item_id=queue_item.queue_item_id,
        content_hash=queue_item.manifest_hash, external_url="https://x.com",
        external_post_id=None, confirmation_note=None, actor="founder",
    )
    # Actor differs but logic says ignore it for identical evidence
    service.confirm_manual_publication(
        mission_id=mission.mission_id, queue_item_id=queue_item.queue_item_id,
        content_hash=queue_item.manifest_hash, external_url="https://x.com",
        external_post_id=None, confirmation_note=None, actor="someone_else",
    )
    # Success

def test_retry_after_status_already_confirmed(service, setup_mission):
    mission, queue_item, _ = setup_mission
    # Manually transition without record to simulate inconsistent state
    queue_item = service.repository.get_publishing_queue_item(queue_item.queue_item_id)
    queue_item.status = PublishingQueueStatus.PUBLISHED_CONFIRMED
    service.repository.update_publishing_queue_item(queue_item)
    
    with pytest.raises(ConflictingDecisionError, match="Inconsistent state: PUBLISHED_CONFIRMED without a durable record"):
        service.confirm_manual_publication(
            mission_id=mission.mission_id, queue_item_id=queue_item.queue_item_id,
            content_hash=queue_item.manifest_hash, external_url="https://x.com",
            external_post_id=None, confirmation_note=None, actor="founder",
        )

def test_changed_evidence_conflicts(service, setup_mission):
    mission, queue_item, _ = setup_mission
    service.confirm_manual_publication(
        mission_id=mission.mission_id, queue_item_id=queue_item.queue_item_id,
        content_hash=queue_item.manifest_hash, external_url="https://x.com",
        external_post_id=None, confirmation_note=None, actor="founder",
    )
    with pytest.raises(ConflictingDecisionError):
        service.confirm_manual_publication(
            mission_id=mission.mission_id, queue_item_id=queue_item.queue_item_id,
            content_hash=queue_item.manifest_hash, external_url="https://x.com/other",
            external_post_id=None, confirmation_note=None, actor="founder",
        )

def test_malformed_inputs(service, setup_mission):
    mission, queue_item, _ = setup_mission
    with pytest.raises(MalformedCommandError, match="Must provide at least one"):
        service.confirm_manual_publication(
            mission_id=mission.mission_id, queue_item_id=queue_item.queue_item_id,
            content_hash=queue_item.manifest_hash, external_url=None,
            external_post_id=None, confirmation_note=None, actor="founder",
        )
    with pytest.raises(MalformedCommandError, match="Invalid URL scheme"):
        service.confirm_manual_publication(
            mission_id=mission.mission_id, queue_item_id=queue_item.queue_item_id,
            content_hash=queue_item.manifest_hash, external_url="ftp://x.com",
            external_post_id=None, confirmation_note=None, actor="founder",
        )

def test_mission_mismatch(service, setup_mission):
    mission, queue_item, _ = setup_mission
    with pytest.raises(MismatchError):
        service.confirm_manual_publication(
            mission_id=uuid4(), queue_item_id=queue_item.queue_item_id,
            content_hash=queue_item.manifest_hash, external_url="https://x.com",
            external_post_id=None, confirmation_note=None, actor="founder",
        )

def test_stale_generation(service, setup_mission):
    mission, queue_item, _ = setup_mission
    mission.publishing_generation += 1
    service.repository.update_mission(mission)
    with pytest.raises(ConflictingDecisionError, match="generation mismatch"):
        service.confirm_manual_publication(
            mission_id=mission.mission_id, queue_item_id=queue_item.queue_item_id,
            content_hash=queue_item.manifest_hash, external_url="https://x.com",
            external_post_id=None, confirmation_note=None, actor="founder",
        )

def test_missing_or_non_approved_approval(service, setup_mission):
    mission, queue_item, approval = setup_mission
    approval.state = "pending"
    service.repository.save_approval(approval)
    with pytest.raises(ConflictingDecisionError):
        service.confirm_manual_publication(
            mission_id=mission.mission_id, queue_item_id=queue_item.queue_item_id,
            content_hash=queue_item.manifest_hash, external_url="https://x.com",
            external_post_id=None, confirmation_note=None, actor="founder",
        )

def test_stale_content_hash(service, setup_mission):
    mission, queue_item, _ = setup_mission
    with pytest.raises(StaleContentError):
        service.confirm_manual_publication(
            mission_id=mission.mission_id, queue_item_id=queue_item.queue_item_id,
            content_hash="b" * 64, external_url="https://x.com",
            external_post_id=None, confirmation_note=None, actor="founder",
        )

def test_database_uniqueness(repo, setup_mission):
    mission, queue_item, _ = setup_mission
    record1 = PublicationRecord(
        mission_id=mission.mission_id, queue_item_id=queue_item.queue_item_id,
        destination="d", content_hash="a"*64, published_by_actor="a",
    )
    repo.save_publication_record(record1)
    record2 = PublicationRecord(
        mission_id=mission.mission_id, queue_item_id=queue_item.queue_item_id,
        destination="d", content_hash="a"*64, published_by_actor="b",
    )
    with pytest.raises(ValueError, match="UNIQUE constraint failed"):
        repo.save_publication_record(record2)

def test_concurrent_collision_identical(service, setup_mission, monkeypatch):
    mission, queue_item, _ = setup_mission
    
    winner = PublicationRecord(
        mission_id=mission.mission_id,
        queue_item_id=queue_item.queue_item_id,
        destination=queue_item.destination,
        content_hash=queue_item.manifest_hash,
        external_url="https://x.com",
        external_post_id=None,
        confirmation_note=None,
        published_by_actor="other",
    )

    def mock_save(record):
        raise ValueError("UNIQUE constraint failed: publication_records.queue_item_id")
        
    call_count = [0]
    def mock_get(queue_item_id):
        call_count[0] += 1
        if call_count[0] == 1:
            return None
        return winner

    monkeypatch.setattr(service.repository, "save_publication_record", mock_save)
    monkeypatch.setattr(service.repository, "get_publication_record", mock_get)
    
    q, pub = service.confirm_manual_publication(
        mission_id=mission.mission_id, queue_item_id=queue_item.queue_item_id,
        content_hash=queue_item.manifest_hash, external_url="https://x.com",
        external_post_id=None, confirmation_note=None, actor="founder",
    )
    assert pub.published_by_actor == "other"

def test_concurrent_collision_conflicting(service, setup_mission, monkeypatch):
    mission, queue_item, _ = setup_mission
    
    winner = PublicationRecord(
        mission_id=mission.mission_id,
        queue_item_id=queue_item.queue_item_id,
        destination=queue_item.destination,
        content_hash=queue_item.manifest_hash,
        external_url="https://DIFFERENT.com",
        published_by_actor="other",
    )

    def mock_save(record):
        raise ValueError("UNIQUE constraint failed: publication_records.queue_item_id")
        
    call_count = [0]
    def mock_get(queue_item_id):
        call_count[0] += 1
        if call_count[0] == 1:
            return None
        return winner

    monkeypatch.setattr(service.repository, "save_publication_record", mock_save)
    monkeypatch.setattr(service.repository, "get_publication_record", mock_get)
    
    with pytest.raises(ConflictingDecisionError, match="concurrent race"):
        service.confirm_manual_publication(
            mission_id=mission.mission_id, queue_item_id=queue_item.queue_item_id,
            content_hash=queue_item.manifest_hash, external_url="https://x.com",
            external_post_id=None, confirmation_note=None, actor="founder",
        )

def test_transaction_rollback(service, setup_mission, monkeypatch):
    mission, queue_item, _ = setup_mission
    
    def mock_append(*args, **kwargs):
        raise RuntimeError("Synthetic append failure")
        
    monkeypatch.setattr(service.repository, "append_event", mock_append)
    
    with pytest.raises(RuntimeError, match="Synthetic append failure"):
        service.confirm_manual_publication(
            mission_id=mission.mission_id, queue_item_id=queue_item.queue_item_id,
            content_hash=queue_item.manifest_hash, external_url="https://x.com",
            external_post_id=None, confirmation_note=None, actor="founder",
        )
    
    # Verify rollback
    assert service.repository.get_publication_record(queue_item.queue_item_id) is None
    q = service.repository.get_publishing_queue_item(queue_item.queue_item_id)
    assert q.status == PublishingQueueStatus.READY_FOR_MANUAL_PUBLISH

def test_dashboard_blocking_reason(service, setup_mission):
    mission, queue_item, _ = setup_mission
    service.confirm_manual_publication(
        mission_id=mission.mission_id, queue_item_id=queue_item.queue_item_id,
        content_hash=queue_item.manifest_hash, external_url="https://x.com",
        external_post_id=None, confirmation_note=None, actor="founder",
    )
    from app.dashboard.operations_v2 import build_operations_projection
    proj = build_operations_projection(service)
    q = proj.publishing_queue[0]
    assert q.is_publication_actionable is False
    assert q.publication_blocking_reason == "Already confirmed."
    
    # Simulate inconsistent state
    from mission_control.repository import SQLiteMissionControlRepository
    service.repository.connection.execute("DELETE FROM publication_records WHERE queue_item_id = ?", (str(queue_item.queue_item_id),))
    
    proj2 = build_operations_projection(service)
    q2 = proj2.publishing_queue[0]
    assert q2.is_publication_actionable is False
    assert q2.publication_blocking_reason == "Inconsistent State: Confirmed status but missing durable record."

def test_no_task_advancement(service, setup_mission):
    mission, queue_item, _ = setup_mission
    service.confirm_manual_publication(
        mission_id=mission.mission_id, queue_item_id=queue_item.queue_item_id,
        content_hash=queue_item.manifest_hash, external_url="https://x.com",
        external_post_id=None, confirmation_note=None, actor="founder",
    )
    
    m = service.repository.get_mission(mission.mission_id)
    assert m.status == mission.status
    assert m.status != "completed"
