"""Mission Control V1 authoritative-kernel tests."""
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from core import DepartmentName, utc_now
from mission_control import (
    ApprovalState, ArtifactRecord, DepartmentResult,
    InMemoryMissionControlRepository, MissionControlService,
    MissionControlStatus, MissionRecord, RiskLevel,
    SQLiteMissionControlRepository, TaskRecord, TaskStatus,
)
from mission_control.compatibility import from_mission_engine
from mission_engine.models import Mission, MissionCapability
from app.main import create_app

HASH = "a" * 64


def mission():
    return MissionRecord(title="Mission", objective="Test the operating kernel", founder_owner="Founder")


def service(repository=None):
    repository=repository or InMemoryMissionControlRepository(); return MissionControlService(repository),repository


def task(value, **changes):
    data=dict(mission_id=value.mission_id,title="Research",department=DepartmentName.RESEARCH,idempotency_key="mission:research")
    data.update(changes); return TaskRecord(**data)


def test_mission_creation_retrieval_and_duplicate_rejection():
    control,repository=service(); value=control.create_mission(mission())
    assert repository.get_mission(value.mission_id)==value
    with pytest.raises(ValueError): control.create_mission(value)


def test_allowed_and_forbidden_transitions():
    control,_=service(); value=control.create_mission(mission())
    assert control.transition(value.mission_id,MissionControlStatus.READY).status==MissionControlStatus.READY
    with pytest.raises(ValueError): control.transition(value.mission_id,MissionControlStatus.COMPLETED)


def test_dependency_ordering_and_blocked_dependency():
    control,repo=service(); value=control.create_mission(mission())
    first=control.add_task(task(value)); second=control.add_task(task(value,title="Write",idempotency_key="mission:write",dependencies=[first.task_id]))
    assert [x.task_id for x in control.next_actions(value.mission_id)]==[first.task_id]
    repo.update_task(first.model_copy(update={"status":TaskStatus.FAILED}))
    assert control.next_actions(value.mission_id)==[]
    assert repo.get_task(second.task_id).status==TaskStatus.BLOCKED


def test_retry_limits_and_idempotent_result():
    control,repo=service(); value=control.create_mission(mission()); item=control.add_task(task(value,maximum_attempts=1))
    command=control.dispatch(item.task_id)
    result=DepartmentResult(command_id=command.command_id,mission_id=value.mission_id,task_id=item.task_id,success=True)
    assert control.accept_result(result).status==TaskStatus.COMPLETED
    assert control.accept_result(result).status==TaskStatus.COMPLETED
    with pytest.raises(ValueError): control.dispatch(item.task_id)


def test_approval_hash_scope_expiry_rejection_and_revocation():
    control,repo=service(); value=control.create_mission(mission())
    item=control.add_task(task(value,consequential=True,required_action="publish",required_artifact_hash=HASH))
    approval=control.request_approval(item)
    assert control.next_actions(value.mission_id)==[]
    approved=control.decide_approval(approval.approval_id,ApprovalState.APPROVED,approver="Founder",reason="Reviewed")
    assert control.has_valid_approval(item)
    assert control.revoke_approval(approved.approval_id,approver="Founder",reason="Changed").state==ApprovalState.REVOKED
    assert not control.has_valid_approval(item)
    rejected=control.request_approval(item)
    assert control.decide_approval(rejected.approval_id,ApprovalState.REJECTED,approver="Founder",reason="No").state==ApprovalState.REJECTED
    wrong=item.model_copy(update={"required_artifact_hash":"b"*64})
    assert not control.has_valid_approval(wrong)
    expired=control.request_approval(item)
    repo.save_approval(expired.model_copy(update={"expires_at":utc_now()-timedelta(seconds=1)}))
    with pytest.raises(ValueError): control.decide_approval(expired.approval_id,ApprovalState.APPROVED,approver="Founder",reason="Late")


def test_artifact_hash_provenance_and_foreign_keys(tmp_path):
    repo=SQLiteMissionControlRepository(tmp_path/"mc.db",allowed_root=tmp_path); control=MissionControlService(repo); value=control.create_mission(mission())
    item=control.add_task(task(value)); artifact=ArtifactRecord(mission_id=value.mission_id,task_id=item.task_id,artifact_type="report",location="artifacts/report.json",content_hash=HASH,provenance={"source":"test"})
    repo.save_artifact(artifact); assert repo.list_artifacts()[0].provenance["source"]=="test"
    with pytest.raises(ValueError): repo.save_task(task(mission()))


def test_sqlite_path_traversal_rejected(tmp_path):
    with pytest.raises(ValueError): SQLiteMissionControlRepository(tmp_path.parent/"outside.db",allowed_root=tmp_path)


def test_event_order_replay_recovery_and_no_consequential_repeat(tmp_path):
    repo=SQLiteMissionControlRepository(tmp_path/"mc.db",allowed_root=tmp_path); control=MissionControlService(repo); value=control.create_mission(mission())
    normal=control.add_task(task(value)); control.dispatch(normal.task_id)
    consequential=control.add_task(task(value,title="Publish",idempotency_key="mission:publish",consequential=True,required_action="publish",required_artifact_hash=HASH))
    repo.update_task(consequential.model_copy(update={"status":TaskStatus.RUNNING,"attempts":1}))
    recovered=control.recover_interrupted(); assert len(recovered)==2
    assert repo.get_task(normal.task_id).status==TaskStatus.RETRY_PENDING
    assert repo.get_task(consequential.task_id).status==TaskStatus.APPROVAL_REQUIRED
    events=control.replay(value.mission_id); assert [e.sequence for e in events]==sorted(e.sequence for e in events)
    assert control.next_actions(value.mission_id)[0].task_id==normal.task_id


def test_projection_and_legacy_compatibility():
    control,_=service(); value=control.create_mission(mission()); control.add_task(task(value,status=TaskStatus.BLOCKED,blocking_reason="wait"))
    projection=control.projection(); assert projection.blocked_tasks and projection.system_health=="operational"
    legacy=Mission(title="Legacy",objective="Preserve APIs",capability=MissionCapability.RESEARCH)
    assert from_mission_engine(legacy,founder_owner="Founder").mission_id==legacy.mission_id


def test_no_external_capability_is_present():
    import mission_control
    names=set(dir(mission_control)); assert not {"crawl","publish","provider","browser"}&names


def test_dashboard_projection_is_read_only_and_injected():
    control,_=service(); control.create_mission(mission())
    client=TestClient(create_app(mission_control_service=control))
    response=client.get("/api/mission-control")
    assert response.status_code==200
    assert response.json()["missions"][0]["title"]=="Mission"
    assert client.post("/api/mission-control").status_code==405
