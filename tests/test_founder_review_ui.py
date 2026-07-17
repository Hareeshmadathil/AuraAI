"""Founder Review & Approval UI V1 integration and safety tests."""
from __future__ import annotations

from datetime import timedelta
import re
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from company_missions.mission_zero_integration import MissionZeroIntegration
from core import utc_now
from mission_control import InMemoryMissionControlRepository, MissionControlService
from mission_control.models import ApprovalState, MissionRecord


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def review_context():
    repository = InMemoryMissionControlRepository()
    control = MissionControlService(repository)
    mission = MissionRecord(
        title="Founder review fixture",
        objective="Review the canonical offline package.",
        founder_owner="Founder",
        founder_goal="Grow AuraAI safely.",
        mission_score=81.5,
        reasoning_summary="Mission lessons changed the score by +2.00: approved quality lesson.",
        required_approvals=["Founder content approval"],
    )
    control.create_mission(mission)
    result = MissionZeroIntegration(control, project_root=ROOT).run(mission)
    quality_task = repository.list_tasks(mission.mission_id)[-2]
    control.register_artifact(
        mission_id=mission.mission_id,
        task_id=quality_task.task_id,
        artifact_type="mission_learning.lesson",
        location="mission-control://lesson",
        value={
            "category": "creative_quality",
            "observation": "Strong quality result.",
            "confidence": 0.9,
            "affected_subsystem": "creative_quality",
        },
        provenance={"evidence_id": "offline-evidence-1", "citation": "fixture://source"},
    )
    client = TestClient(
        create_app(
            dashboard_service=result.dashboard_service,
            mission_control_service=control,
        )
    )
    return client, control, result


def _form(client, result, *, decision="approved", **changes):
    path = f"/missions/{result.mission_id}/review"
    page = client.get(path)
    token = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
    approval = result.approval_request
    data = {
        "csrf_token": token,
        "approval_id": str(approval.approval_id),
        "task_id": str(approval.task_id),
        "requested_action": approval.requested_action,
        "content_hash": approval.content_hash,
        "decision": decision,
        "reason": "Founder reviewed the exact offline package.",
    }
    data.update(changes)
    return path, data


def test_page_renders_canonical_persisted_state(review_context):
    client, _, result = review_context
    response = client.get(f"/missions/{result.mission_id}/review")
    assert response.status_code == 200
    for text in (
        "Grow AuraAI safely.", "81.50", "SHA-256", "Creative Quality",
        "offline-evidence-1", "Mission lessons changed the score by +2.00",
        str(result.approval_request.approval_id), "NO RENDER", "NO PUBLISH",
    ):
        assert text in response.text
    assert "C:\\Projects" not in response.text


def test_approval_uses_exact_request_and_hash(review_context):
    client, control, result = review_context
    path, data = _form(client, result)
    response = client.post(f"{path}/decision", data=data, follow_redirects=False)
    assert response.status_code == 303
    stored = control.repository.get_approval(result.approval_request.approval_id)
    assert stored.state == ApprovalState.APPROVED
    assert stored.content_hash == data["content_hash"]
    assert control.repository.get_mission(result.approval_request.mission_id).status.value == "completed"


def test_hash_mismatch_and_duplicate_decision_fail(review_context):
    client, _, result = review_context
    path, data = _form(client, result, content_hash="0" * 64)
    assert client.post(f"{path}/decision", data=data).status_code == 409
    path, data = _form(client, result)
    assert client.post(f"{path}/decision", data=data, follow_redirects=False).status_code == 303
    assert client.post(f"{path}/decision", data=data).status_code == 409


def test_expired_and_revoked_requests_fail(review_context):
    client, control, result = review_context
    approval = result.approval_request
    control.repository.save_approval(approval.model_copy(update={
        "expires_at": approval.issued_at + timedelta(microseconds=1),
    }))
    path, data = _form(client, result)
    assert client.post(f"{path}/decision", data=data).status_code == 409

    control.repository.save_approval(approval.model_copy(update={"state": ApprovalState.REVOKED}))
    assert client.post(f"{path}/decision", data=data).status_code == 409


@pytest.mark.parametrize("decision", ["rejected", "revision_requested"])
def test_rejection_and_revision_are_persisted(review_context, decision):
    client, control, result = review_context
    artifacts_before = [item.content_hash for item in control.repository.list_artifacts()]
    path, data = _form(client, result, decision=decision, reason=f"Founder {decision} reason")
    response = client.post(f"{path}/decision", data=data, follow_redirects=False)
    assert response.status_code == 303
    approval = control.repository.get_approval(result.approval_request.approval_id)
    assert approval.state.value == decision
    assert approval.reason == f"Founder {decision} reason"
    assert [item.content_hash for item in control.repository.list_artifacts()] == artifacts_before
    events = control.repository.list_events(approval.mission_id)
    assert events[-1].event_type == "founder.decision"
    assert events[-1].payload["decision"] == decision


def test_csrf_get_and_invalid_identifiers_fail_safely(review_context):
    client, _, result = review_context
    path, data = _form(client, result)
    data["csrf_token"] = "x" * 32
    assert client.post(f"{path}/decision", data=data).status_code == 403
    assert client.get(f"{path}/decision").status_code == 405
    assert client.get(f"/missions/{uuid4()}/review").status_code == 404
    assert client.get("/missions/not-a-uuid/review").status_code == 422


def test_decisions_do_not_trigger_external_operations(review_context, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("External operation attempted.")

    monkeypatch.setattr("web_intelligence.service.WebIntelligenceService.execute", forbidden)
    monkeypatch.setattr("providers.gemini.transport.UnavailableGeminiTransport.send", forbidden)
    monkeypatch.setattr("private_video_production.render.service.PrivateRenderService.render", forbidden)
    client, _, result = review_context
    path, data = _form(client, result, decision="revision_requested")
    assert client.post(f"{path}/decision", data=data, follow_redirects=False).status_code == 303
    tracked = subprocess.run(
        ["git", "ls-files", "founder_inputs/mission_zero.json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert tracked.stdout.strip() == ""
