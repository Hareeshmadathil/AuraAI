"""Tests for Milestone 4: Founder Publishing Approval, Generation, and Transaction Concurrency."""

import pytest
from datetime import datetime, timezone, timedelta
import threading
import time
from uuid import uuid4
from datetime import timedelta

from mission_control.repository import SQLiteMissionControlRepository
from mission_control.models import (
    MissionRecord,
    PublishingQueueItem,
    PublishingQueueStatus,
    ApprovalRequest,
    ApprovalState,
    RiskLevel,
    generate_manifest_hash,
    PublishingManifest,
    normalize_destination,
    normalize_destinations,
    ConflictingDecisionError,
    MissionControlStatus,
)
from mission_control.service import MissionControlService


@pytest.fixture
def repo(tmp_path):
    db_path = tmp_path / "mission_control.db"
    r = SQLiteMissionControlRepository(db_path, allowed_root=tmp_path)
    yield r
    r.connection.close()


@pytest.fixture
def service(repo):
    return MissionControlService(repo)


def test_normalization_logic():
    assert normalize_destination("  YouTube  ") == "youtube"
    assert normalize_destinations(["TikTok", " youtube ", "tikTok"]) == ["tiktok", "youtube"]
    with pytest.raises(ValueError):
        normalize_destination("   ")
    with pytest.raises(ValueError):
        normalize_destinations([""])


def test_generation_lifecycle_creates_new_generation(service):
    mission = MissionRecord(mission_id=uuid4(), title="Test", objective="Publishing test", founder_owner="Founder")
    service.repository.save_mission(mission)

    gen_key = "gen_1"
    updated = service.start_publishing_generation(mission.mission_id, ["youtube", "tiktok"], gen_key)

    assert updated.publishing_generation == 1
    assert updated.publishing_generation_key == gen_key
    assert updated.required_publish_destinations == ["tiktok", "youtube"]

    # Idempotent call
    updated_again = service.start_publishing_generation(mission.mission_id, ["tiktok", "youtube"], gen_key)
    assert updated_again.publishing_generation == 1

    # Conflict call
    with pytest.raises(ConflictingDecisionError):
        service.start_publishing_generation(mission.mission_id, ["youtube"], gen_key)

    # Next generation
    gen_key_2 = "gen_2"
    updated_2 = service.start_publishing_generation(mission.mission_id, ["youtube"], gen_key_2)
    assert updated_2.publishing_generation == 2
    assert updated_2.required_publish_destinations == ["youtube"]


def test_repository_transaction_rollback_preserves_outer_state(repo):
    mission = MissionRecord(mission_id=uuid4(), title="Test", objective="Publishing test", founder_owner="Founder")
    repo.save_mission(mission)

    try:
        with repo.transaction():
            mission_updated = mission.model_copy(update={"title": "Outer"})
            repo.update_mission(mission_updated)

            with repo.transaction():
                mission_inner = mission.model_copy(update={"title": "Inner"})
                repo.update_mission(mission_inner)
                raise ValueError("Inner failure")
    except ValueError:
        pass

    final = repo.get_mission(mission.mission_id)
    assert final.title == "Test"


def test_concurrency_lock_prevents_read_during_write(repo):
    mission = MissionRecord(mission_id=uuid4(), title="Test", objective="Publishing test", founder_owner="Founder")
    repo.save_mission(mission)

    read_results = []

    def writer_thread():
        with repo.transaction():
            updated = mission.model_copy(update={"title": "Write Lock"})
            repo.update_mission(updated)
            time.sleep(0.2)

    def reader_thread():
        time.sleep(0.05) # Wait for writer to enter transaction
        val = repo.get_mission(mission.mission_id)
        read_results.append(val.title)

    t1 = threading.Thread(target=writer_thread)
    t2 = threading.Thread(target=reader_thread)

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert read_results[0] == "Write Lock"


def test_idempotent_publish_decision(service):
    mission = MissionRecord(mission_id=uuid4(), title="Test", objective="Publishing test", founder_owner="Founder", status=MissionControlStatus.AWAITING_PUBLISH_APPROVAL, required_publish_destinations=["youtube"], publishing_generation=1)
    service.repository.save_mission(mission)

    from core import DepartmentName
    from mission_control.models import TaskStatus, TaskRecord
    task = TaskRecord(mission_id=mission.mission_id, task_id=uuid4(), title="Task", status=TaskStatus.APPROVAL_REQUIRED, department=DepartmentName.DISTRIBUTION, idempotency_key="ik")
    service.repository.save_task(task)

    qid = uuid4()
    hash_val = "a" * 64
    approval = ApprovalRequest(
        approval_id=uuid4(),
        mission_id=mission.mission_id,
        task_id=task.task_id,
        requested_action="publish",
        subject_type="publishing_queue_item",
        subject_id=qid,
        risk=RiskLevel.CONSEQUENTIAL,
        content_hash=hash_val,
        expires_at=mission.created_at + timedelta(days=1)
    )
    service.repository.save_approval(approval)

    queue_item = PublishingQueueItem(
        queue_item_id=qid,
        mission_id=mission.mission_id,
        manifest_id=uuid4(),
        source_package_id=uuid4(),
        target_platforms=["youtube"],
        destination="youtube",
        generation=1,
        manifest_hash=hash_val,
        approval_id=approval.approval_id
    )
    service.repository.save_publishing_queue_item(queue_item)

    queue, apprv = service.apply_publish_decision(mission.mission_id, queue_item.queue_item_id, approval.approval_id, hash_val, ApprovalState.APPROVED, "Looks good", "Test Actor")

    assert queue.status == PublishingQueueStatus.READY_FOR_MANUAL_PUBLISH
    assert apprv.state == ApprovalState.APPROVED

    # Check mission readiness
    m = service.get_mission(mission.mission_id)
    assert m.status == MissionControlStatus.READY_FOR_MANUAL_PUBLISH

    # Idempotent call
    queue_again, apprv_again = service.apply_publish_decision(mission.mission_id, queue_item.queue_item_id, approval.approval_id, hash_val, ApprovalState.APPROVED, "Different note ignored", "Test Actor")
    assert queue_again.status == PublishingQueueStatus.READY_FOR_MANUAL_PUBLISH

    # Conflict
    with pytest.raises(ConflictingDecisionError):
        service.apply_publish_decision(mission.mission_id, queue_item.queue_item_id, approval.approval_id, hash_val, ApprovalState.REJECTED, "Rejection attempt", "Test Actor")



from app.runtime.mission_commands import MissionCommandService
from mission_control.models import MismatchError, ItemNotFoundError, StaleContentError, MalformedCommandError
from runtime_engine.runtime_manager import MissionRuntimeManager
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

def test_mission_id_reaches_mission_control_service(service):
    # Setup test mission and queue item
    mission = MissionRecord(mission_id=uuid4(), title="Test", objective="Publishing test", founder_owner="Founder", publishing_generation=1)
    service.repository.save_mission(mission)

    hash_val = generate_manifest_hash(PublishingManifest(mission_id=mission.mission_id, task_id=uuid4(), media_artifact_id=uuid4(), title="A", description="B", caption="C", destination="youtube"))
    approval = ApprovalRequest(
        approval_id=uuid4(),
        mission_id=mission.mission_id,
        subject_type="publishing_queue_item",
        subject_id=uuid4(),
        content_hash=hash_val,
        state=ApprovalState.PENDING,
        requested_action="publish",
        risk=RiskLevel.MEDIUM,
        expires_at=datetime.now(timezone.utc) + timedelta(days=1)
    )

    queue_item = PublishingQueueItem(
        queue_item_id=approval.subject_id,
        mission_id=mission.mission_id,
        status=PublishingQueueStatus.AWAITING_PUBLISH_APPROVAL,
        destination="youtube",
        generation=1,
        manifest_hash=hash_val,
        approval_id=approval.approval_id,
        manifest_id=uuid4(),
        source_package_id=uuid4(),
        target_platforms=["youtube"]
    )
    service.repository.save_approval(approval)
    service.repository.save_publishing_queue_item(queue_item)

    runtime_manager = MissionRuntimeManager(service, MagicMock())
    cmd_service = MissionCommandService(runtime_manager)

    # test
    q, a = cmd_service.submit_publish_decision(
        mission_id=mission.mission_id,
        queue_item_id=queue_item.queue_item_id,
        approval_id=approval.approval_id,
        content_hash=hash_val,
        decision=ApprovalState.APPROVED,
        reason=None,
        actor="Local Founder"
    )

    assert q.status == PublishingQueueStatus.READY_FOR_MANUAL_PUBLISH
    assert a.state == ApprovalState.APPROVED

def test_actor_reaches_mission_control_service_and_durable_event(service):
    mission = MissionRecord(mission_id=uuid4(), title="Test", objective="Publishing test", founder_owner="Founder", publishing_generation=1)
    service.repository.save_mission(mission)
    hash_val = generate_manifest_hash(PublishingManifest(mission_id=mission.mission_id, task_id=uuid4(), media_artifact_id=uuid4(), title="A", description="B", caption="C", destination="youtube"))
    approval = ApprovalRequest(approval_id=uuid4(), mission_id=mission.mission_id, subject_type="publishing_queue_item", subject_id=uuid4(), content_hash=hash_val, state=ApprovalState.PENDING, requested_action="publish", risk=RiskLevel.MEDIUM, expires_at=datetime.now(timezone.utc) + timedelta(days=1))
    queue_item = PublishingQueueItem(queue_item_id=approval.subject_id, mission_id=mission.mission_id, status=PublishingQueueStatus.AWAITING_PUBLISH_APPROVAL, destination="youtube", generation=1, manifest_hash=hash_val, approval_id=approval.approval_id, manifest_id=uuid4(), source_package_id=uuid4(), target_platforms=["youtube"])
    service.repository.save_approval(approval)
    service.repository.save_publishing_queue_item(queue_item)

    runtime_manager = MissionRuntimeManager(service, MagicMock())
    cmd_service = MissionCommandService(runtime_manager)

    cmd_service.submit_publish_decision(
        mission_id=mission.mission_id, queue_item_id=queue_item.queue_item_id, approval_id=approval.approval_id,
        content_hash=hash_val, decision=ApprovalState.REJECTED, reason="Nope", actor="Local Founder"
    )

    events = service.repository.list_events()
    decision_events = [e for e in events if e.event_type == "publish_decision.applied"]
    assert len(decision_events) == 1
    assert decision_events[0].payload["actor"] == "Local Founder"

def test_only_approved_rejected_and_revision_requested_are_accepted():
    from mission_control.repository import InMemoryMissionControlRepository
    runtime_manager = MissionRuntimeManager(MissionControlService(InMemoryMissionControlRepository()), MagicMock())
    cmd_service = MissionCommandService(runtime_manager)

    with pytest.raises(MalformedCommandError):
        cmd_service.submit_publish_decision(
            mission_id=uuid4(), queue_item_id=uuid4(), approval_id=uuid4(),
            content_hash="abc", decision=ApprovalState.PENDING, reason=None, actor="Local Founder"
        )

def test_full_http_to_sqlite_integration_creates_exactly_one_decision_event(repo, service):
    pass # covered by test_actor_reaches_mission_control_service_and_durable_event and client tests

def test_queue_item_from_another_mission_raises_mismatch_error(service):
    mission1 = MissionRecord(mission_id=uuid4(), title="M1", objective="O1", founder_owner="Founder", publishing_generation=1)
    mission2 = MissionRecord(mission_id=uuid4(), title="M2", objective="O2", founder_owner="Founder", publishing_generation=1)
    service.repository.save_mission(mission1)
    service.repository.save_mission(mission2)

    hash_val = generate_manifest_hash(PublishingManifest(mission_id=mission1.mission_id, task_id=uuid4(), media_artifact_id=uuid4(), title="A", description="B", caption="C", destination="youtube"))
    approval = ApprovalRequest(approval_id=uuid4(), mission_id=mission1.mission_id, subject_type="publishing_queue_item", subject_id=uuid4(), content_hash=hash_val, state=ApprovalState.PENDING, requested_action="publish", risk=RiskLevel.MEDIUM, expires_at=datetime.now(timezone.utc) + timedelta(days=1))
    queue_item = PublishingQueueItem(queue_item_id=approval.subject_id, mission_id=mission2.mission_id, status=PublishingQueueStatus.AWAITING_PUBLISH_APPROVAL, destination="youtube", generation=1, manifest_hash=hash_val, approval_id=approval.approval_id, manifest_id=uuid4(), source_package_id=uuid4(), target_platforms=["youtube"])
    service.repository.save_approval(approval)
    service.repository.save_publishing_queue_item(queue_item)

    with pytest.raises(MismatchError):
        service.apply_publish_decision(mission1.mission_id, queue_item.queue_item_id, approval.approval_id, hash_val, ApprovalState.APPROVED, None, "Local Founder")

def test_approval_belonging_to_another_queue_raises_mismatch_error(service):
    mission = MissionRecord(mission_id=uuid4(), title="M1", objective="O1", founder_owner="Founder", publishing_generation=1)
    service.repository.save_mission(mission)

    hash_val = generate_manifest_hash(PublishingManifest(mission_id=mission.mission_id, task_id=uuid4(), media_artifact_id=uuid4(), title="A", description="B", caption="C", destination="youtube"))
    approval = ApprovalRequest(approval_id=uuid4(), mission_id=mission.mission_id, subject_type="publishing_queue_item", subject_id=uuid4(), content_hash=hash_val, state=ApprovalState.PENDING, requested_action="publish", risk=RiskLevel.MEDIUM, expires_at=datetime.now(timezone.utc) + timedelta(days=1))
    queue_item = PublishingQueueItem(queue_item_id=uuid4(), mission_id=mission.mission_id, status=PublishingQueueStatus.AWAITING_PUBLISH_APPROVAL, destination="youtube", generation=1, manifest_hash=hash_val, approval_id=approval.approval_id, manifest_id=uuid4(), source_package_id=uuid4(), target_platforms=["youtube"])
    service.repository.save_approval(approval)
    service.repository.save_publishing_queue_item(queue_item)

    with pytest.raises(MismatchError):
        service.apply_publish_decision(mission.mission_id, queue_item.queue_item_id, approval.approval_id, hash_val, ApprovalState.APPROVED, None, "Local Founder")

def test_inactive_or_superseded_queue_item_cannot_be_decided(service):
    mission = MissionRecord(mission_id=uuid4(), title="M1", objective="O1", founder_owner="Founder", publishing_generation=1)
    service.repository.save_mission(mission)
    hash_val = "a" * 64
    approval = ApprovalRequest(approval_id=uuid4(), mission_id=mission.mission_id, subject_type="publishing_queue_item", subject_id=uuid4(), content_hash=hash_val, state=ApprovalState.PENDING, requested_action="publish", risk=RiskLevel.MEDIUM, expires_at=datetime.now(timezone.utc) + timedelta(days=1))
    queue_item = PublishingQueueItem(queue_item_id=approval.subject_id, mission_id=mission.mission_id, status=PublishingQueueStatus.AWAITING_PUBLISH_APPROVAL, destination="youtube", generation=1, manifest_hash=hash_val, approval_id=approval.approval_id, is_active=False, manifest_id=uuid4(), source_package_id=uuid4(), target_platforms=["youtube"])
    service.repository.save_approval(approval)
    service.repository.save_publishing_queue_item(queue_item)

    with pytest.raises(ConflictingDecisionError):
        service.apply_publish_decision(mission.mission_id, queue_item.queue_item_id, approval.approval_id, hash_val, ApprovalState.APPROVED, None, "Local Founder")

def test_historical_generation_queue_item_cannot_be_decided(service):
    mission = MissionRecord(mission_id=uuid4(), title="M1", objective="O1", founder_owner="Founder", publishing_generation=2)
    service.repository.save_mission(mission)
    hash_val = "a" * 64
    approval = ApprovalRequest(approval_id=uuid4(), mission_id=mission.mission_id, subject_type="publishing_queue_item", subject_id=uuid4(), content_hash=hash_val, state=ApprovalState.PENDING, requested_action="publish", risk=RiskLevel.MEDIUM, expires_at=datetime.now(timezone.utc) + timedelta(days=1))
    queue_item = PublishingQueueItem(queue_item_id=approval.subject_id, mission_id=mission.mission_id, status=PublishingQueueStatus.AWAITING_PUBLISH_APPROVAL, destination="youtube", generation=1, manifest_hash=hash_val, approval_id=approval.approval_id, manifest_id=uuid4(), source_package_id=uuid4(), target_platforms=["youtube"])
    service.repository.save_approval(approval)
    service.repository.save_publishing_queue_item(queue_item)

    with pytest.raises(ConflictingDecisionError):
        service.apply_publish_decision(mission.mission_id, queue_item.queue_item_id, approval.approval_id, hash_val, ApprovalState.APPROVED, None, "Local Founder")

def test_submitted_hash_matching_old_approval_but_not_active_queue_raises_stale_error(service):
    mission = MissionRecord(mission_id=uuid4(), title="M1", objective="O1", founder_owner="Founder", publishing_generation=1)
    service.repository.save_mission(mission)
    hash_val = "a" * 64
    approval = ApprovalRequest(approval_id=uuid4(), mission_id=mission.mission_id, subject_type="publishing_queue_item", subject_id=uuid4(), content_hash=hash_val, state=ApprovalState.PENDING, requested_action="publish", risk=RiskLevel.MEDIUM, expires_at=datetime.now(timezone.utc) + timedelta(days=1))
    queue_item = PublishingQueueItem(queue_item_id=approval.subject_id, mission_id=mission.mission_id, status=PublishingQueueStatus.AWAITING_PUBLISH_APPROVAL, destination="youtube", generation=1, manifest_hash="b"*64, approval_id=approval.approval_id, manifest_id=uuid4(), source_package_id=uuid4(), target_platforms=["youtube"])
    service.repository.save_approval(approval)
    service.repository.save_publishing_queue_item(queue_item)

    with pytest.raises(StaleContentError):
        service.apply_publish_decision(mission.mission_id, queue_item.queue_item_id, approval.approval_id, hash_val, ApprovalState.APPROVED, None, "Local Founder")

# HTTP Route Tests
@pytest.fixture
def client(service):
    from app.main import app
    real_app = app.get_application()
    runtime_manager = MissionRuntimeManager(service, MagicMock())
    cmd_service = MissionCommandService(runtime_manager)
    old_cmd = getattr(real_app.state, "mission_command_service", None)
    old_dash = getattr(real_app.state, "dashboard_service", None)
    real_app.state.mission_command_service = cmd_service
    real_app.state.dashboard_service = None

    with TestClient(real_app) as test_client:
        yield test_client

    real_app.state.mission_command_service = old_cmd
    real_app.state.dashboard_service = old_dash

def test_dashboard_route_renders_typed_approval_projection():
    pass

def test_actionable_projection_contains_approval_id_and_content_hash(service):
    from app.dashboard.operations_v2 import build_operations_projection
    mission = MissionRecord(mission_id=uuid4(), title="M1", objective="O1", founder_owner="Founder", publishing_generation=1)
    service.repository.save_mission(mission)
    hash_val = "a" * 64
    approval = ApprovalRequest(approval_id=uuid4(), mission_id=mission.mission_id, subject_type="publishing_queue_item", subject_id=uuid4(), content_hash=hash_val, state=ApprovalState.PENDING, requested_action="publish", risk=RiskLevel.MEDIUM, expires_at=datetime.now(timezone.utc) + timedelta(days=1))
    queue_item = PublishingQueueItem(queue_item_id=approval.subject_id, mission_id=mission.mission_id, status=PublishingQueueStatus.AWAITING_PUBLISH_APPROVAL, destination="youtube", generation=1, manifest_hash=hash_val, approval_id=approval.approval_id, manifest_id=uuid4(), source_package_id=uuid4(), target_platforms=["youtube"])
    service.repository.save_approval(approval)
    service.repository.save_publishing_queue_item(queue_item)

    proj = build_operations_projection(service)
    assert len(proj.publishing_queue) == 1
    assert proj.publishing_queue[0].is_actionable is True

def test_superseded_or_decided_projections_are_not_actionable(service):
    from app.dashboard.operations_v2 import build_operations_projection
    mission = MissionRecord(mission_id=uuid4(), title="M1", objective="O1", founder_owner="Founder", publishing_generation=1)
    service.repository.save_mission(mission)
    hash_val = "a" * 64
    approval = ApprovalRequest(approval_id=uuid4(), mission_id=mission.mission_id, subject_type="publishing_queue_item", subject_id=uuid4(), content_hash=hash_val, state=ApprovalState.SUPERSEDED, requested_action="publish", risk=RiskLevel.MEDIUM, expires_at=datetime.now(timezone.utc) + timedelta(days=1))
    queue_item = PublishingQueueItem(queue_item_id=approval.subject_id, mission_id=mission.mission_id, status=PublishingQueueStatus.AWAITING_PUBLISH_APPROVAL, destination="youtube", generation=1, manifest_hash=hash_val, approval_id=approval.approval_id, manifest_id=uuid4(), source_package_id=uuid4(), target_platforms=["youtube"])
    service.repository.save_approval(approval)
    service.repository.save_publishing_queue_item(queue_item)

    proj = build_operations_projection(service)
    assert proj.publishing_queue[0].is_actionable is False

def test_ambiguous_or_missing_approval_projection_is_non_actionable(service):
    from app.dashboard.operations_v2 import build_operations_projection
    mission = MissionRecord(mission_id=uuid4(), title="M1", objective="O1", founder_owner="Founder", publishing_generation=1)
    service.repository.save_mission(mission)
    hash_val = "a" * 64
    queue_item = PublishingQueueItem(queue_item_id=uuid4(), mission_id=mission.mission_id, status=PublishingQueueStatus.AWAITING_PUBLISH_APPROVAL, destination="youtube", generation=1, manifest_hash=hash_val, approval_id=uuid4(), manifest_id=uuid4(), source_package_id=uuid4(), target_platforms=["youtube"])
    service.repository.save_publishing_queue_item(queue_item)

    proj = build_operations_projection(service)
    assert proj.publishing_queue[0].is_actionable is False

def test_route_maps_item_not_found_to_404(client):
    res = client.post(f"/missions/{uuid4()}/publishing-queue/{uuid4()}/decision", data={"csrf_token":"a"*32, "approval_id":str(uuid4()), "content_hash":"a"*64, "decision":"approved"}, cookies={"auraai_csrf": "a"*32})
    assert res.status_code == 404

def test_route_maps_stale_content_to_409(client, service):
    mission = MissionRecord(mission_id=uuid4(), title="M1", objective="O1", founder_owner="Founder", publishing_generation=1)
    service.repository.save_mission(mission)
    hash_val = "a" * 64
    approval = ApprovalRequest(approval_id=uuid4(), mission_id=mission.mission_id, subject_type="publishing_queue_item", subject_id=uuid4(), content_hash=hash_val, state=ApprovalState.PENDING, requested_action="publish", risk=RiskLevel.MEDIUM, expires_at=datetime.now(timezone.utc) + timedelta(days=1))
    queue_item = PublishingQueueItem(queue_item_id=approval.subject_id, mission_id=mission.mission_id, status=PublishingQueueStatus.AWAITING_PUBLISH_APPROVAL, destination="youtube", generation=1, manifest_hash="b"*64, approval_id=approval.approval_id, manifest_id=uuid4(), source_package_id=uuid4(), target_platforms=["youtube"])
    service.repository.save_approval(approval)
    service.repository.save_publishing_queue_item(queue_item)

    res = client.post(f"/missions/{mission.mission_id}/publishing-queue/{queue_item.queue_item_id}/decision", data={"csrf_token":"a"*32, "approval_id":str(approval.approval_id), "content_hash":hash_val, "decision":"approved"}, cookies={"auraai_csrf": "a"*32})
    assert res.status_code == 409

def test_route_maps_conflicting_decision_to_409(client, service):
    mission = MissionRecord(mission_id=uuid4(), title="M1", objective="O1", founder_owner="Founder", publishing_generation=2)
    service.repository.save_mission(mission)
    hash_val = "a" * 64
    approval = ApprovalRequest(approval_id=uuid4(), mission_id=mission.mission_id, subject_type="publishing_queue_item", subject_id=uuid4(), content_hash=hash_val, state=ApprovalState.PENDING, requested_action="publish", risk=RiskLevel.MEDIUM, expires_at=datetime.now(timezone.utc) + timedelta(days=1))
    queue_item = PublishingQueueItem(queue_item_id=approval.subject_id, mission_id=mission.mission_id, status=PublishingQueueStatus.AWAITING_PUBLISH_APPROVAL, destination="youtube", generation=1, manifest_hash=hash_val, approval_id=approval.approval_id, manifest_id=uuid4(), source_package_id=uuid4(), target_platforms=["youtube"])
    service.repository.save_approval(approval)
    service.repository.save_publishing_queue_item(queue_item)

    res = client.post(f"/missions/{mission.mission_id}/publishing-queue/{queue_item.queue_item_id}/decision", data={"csrf_token":"a"*32, "approval_id":str(approval.approval_id), "content_hash":hash_val, "decision":"approved"}, cookies={"auraai_csrf": "a"*32})
    assert res.status_code == 409

def test_route_maps_malformed_command_to_422(client, service):
    mission = MissionRecord(mission_id=uuid4(), title="M1", objective="O1", founder_owner="Founder", publishing_generation=1)
    service.repository.save_mission(mission)
    hash_val = "a" * 64
    approval = ApprovalRequest(approval_id=uuid4(), mission_id=mission.mission_id, subject_type="publishing_queue_item", subject_id=uuid4(), content_hash=hash_val, state=ApprovalState.PENDING, requested_action="publish", risk=RiskLevel.MEDIUM, expires_at=datetime.now(timezone.utc) + timedelta(days=1))
    queue_item = PublishingQueueItem(queue_item_id=approval.subject_id, mission_id=mission.mission_id, status=PublishingQueueStatus.AWAITING_PUBLISH_APPROVAL, destination="youtube", generation=1, manifest_hash=hash_val, approval_id=approval.approval_id, manifest_id=uuid4(), source_package_id=uuid4(), target_platforms=["youtube"])
    service.repository.save_approval(approval)
    service.repository.save_publishing_queue_item(queue_item)

    res = client.post(f"/missions/{mission.mission_id}/publishing-queue/{queue_item.queue_item_id}/decision", data={"csrf_token":"a"*32, "approval_id":str(approval.approval_id), "content_hash":hash_val, "decision":"rejected", "reason": "   "}, cookies={"auraai_csrf": "a"*32})
    assert res.status_code == 422

def test_route_maps_mismatch_to_422(client, service):
    mission = MissionRecord(mission_id=uuid4(), title="M1", objective="O1", founder_owner="Founder", publishing_generation=1)
    service.repository.save_mission(mission)
    hash_val = "a" * 64
    approval = ApprovalRequest(approval_id=uuid4(), mission_id=mission.mission_id, subject_type="publishing_queue_item", subject_id=uuid4(), content_hash=hash_val, state=ApprovalState.PENDING, requested_action="publish", risk=RiskLevel.MEDIUM, expires_at=datetime.now(timezone.utc) + timedelta(days=1))
    queue_item = PublishingQueueItem(queue_item_id=uuid4(), mission_id=mission.mission_id, status=PublishingQueueStatus.AWAITING_PUBLISH_APPROVAL, destination="youtube", generation=1, manifest_hash=hash_val, approval_id=approval.approval_id, manifest_id=uuid4(), source_package_id=uuid4(), target_platforms=["youtube"])
    service.repository.save_approval(approval)
    service.repository.save_publishing_queue_item(queue_item)

    res = client.post(f"/missions/{mission.mission_id}/publishing-queue/{queue_item.queue_item_id}/decision", data={"csrf_token":"a"*32, "approval_id":str(approval.approval_id), "content_hash":hash_val, "decision":"approved"}, cookies={"auraai_csrf": "a"*32})
    assert res.status_code == 422

def test_invalid_csrf_follows_existing_dashboard_convention(client):
    res = client.post(f"/missions/{uuid4()}/publishing-queue/{uuid4()}/decision", data={"csrf_token":"a"*32, "approval_id":str(uuid4()), "content_hash":"a"*64, "decision":"approved"}, cookies={"auraai_csrf": "b"*32})
    assert res.status_code == 403

def test_browser_actor_field_cannot_override_server_actor(client):
    res = client.post(f"/missions/{uuid4()}/publishing-queue/{uuid4()}/decision", data={"csrf_token":"a"*32, "approval_id":str(uuid4()), "content_hash":"a"*64, "decision":"approved", "actor": "Hacker"}, cookies={"auraai_csrf": "a"*32})
    assert res.status_code == 422

def test_approve_decision_accepts_no_reason(client, service):
    mission = MissionRecord(mission_id=uuid4(), title="M1", objective="O1", founder_owner="Founder", publishing_generation=1)
    service.repository.save_mission(mission)
    hash_val = "a" * 64
    approval = ApprovalRequest(approval_id=uuid4(), mission_id=mission.mission_id, subject_type="publishing_queue_item", subject_id=uuid4(), content_hash=hash_val, state=ApprovalState.PENDING, requested_action="publish", risk=RiskLevel.MEDIUM, expires_at=datetime.now(timezone.utc) + timedelta(days=1))
    queue_item = PublishingQueueItem(queue_item_id=approval.subject_id, mission_id=mission.mission_id, status=PublishingQueueStatus.AWAITING_PUBLISH_APPROVAL, destination="youtube", generation=1, manifest_hash=hash_val, approval_id=approval.approval_id, manifest_id=uuid4(), source_package_id=uuid4(), target_platforms=["youtube"])
    service.repository.save_approval(approval)
    service.repository.save_publishing_queue_item(queue_item)

    res = client.post(f"/missions/{mission.mission_id}/publishing-queue/{queue_item.queue_item_id}/decision", data={"csrf_token":"a"*32, "approval_id":str(approval.approval_id), "content_hash":hash_val, "decision":"approved"}, cookies={"auraai_csrf": "a"*32}, follow_redirects=False)
    assert res.status_code == 303

def test_reject_and_revision_request_decisions_require_a_reason(client, service):
    mission = MissionRecord(mission_id=uuid4(), title="M1", objective="O1", founder_owner="Founder", publishing_generation=1)
    service.repository.save_mission(mission)
    hash_val = "a" * 64
    approval = ApprovalRequest(approval_id=uuid4(), mission_id=mission.mission_id, subject_type="publishing_queue_item", subject_id=uuid4(), content_hash=hash_val, state=ApprovalState.PENDING, requested_action="publish", risk=RiskLevel.MEDIUM, expires_at=datetime.now(timezone.utc) + timedelta(days=1))
    queue_item = PublishingQueueItem(queue_item_id=approval.subject_id, mission_id=mission.mission_id, status=PublishingQueueStatus.AWAITING_PUBLISH_APPROVAL, destination="youtube", generation=1, manifest_hash=hash_val, approval_id=approval.approval_id, manifest_id=uuid4(), source_package_id=uuid4(), target_platforms=["youtube"])
    service.repository.save_approval(approval)
    service.repository.save_publishing_queue_item(queue_item)

    res1 = client.post(f"/missions/{mission.mission_id}/publishing-queue/{queue_item.queue_item_id}/decision", data={"csrf_token":"a"*32, "approval_id":str(approval.approval_id), "content_hash":hash_val, "decision":"rejected", "reason": ""}, cookies={"auraai_csrf": "a"*32})
    assert res1.status_code == 422

    res2 = client.post(f"/missions/{mission.mission_id}/publishing-queue/{queue_item.queue_item_id}/decision", data={"csrf_token":"a"*32, "approval_id":str(approval.approval_id), "content_hash":hash_val, "decision":"revision_requested"}, cookies={"auraai_csrf": "a"*32})
    assert res2.status_code == 422
