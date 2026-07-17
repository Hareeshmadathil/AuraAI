"""Dashboard Operations V2 persisted read-projection tests."""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import subprocess

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from company_missions.mission_zero_integration import MissionZeroIntegration
from core import utc_now
from mission_control import InMemoryMissionControlRepository, MissionControlService
from mission_control.models import ApprovalRequest, RiskLevel


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def operations_context():
    control = MissionControlService(InMemoryMissionControlRepository())
    result = MissionZeroIntegration(control, project_root=ROOT).run()
    mission_id = result.approval_request.mission_id
    task_id = control.repository.list_tasks(mission_id)[-2].task_id
    values = (
        ("canonical_evidence", {"rank_score": 82, "citation": "fixture://evidence"}),
        ("content_intelligence", {"recommendation": "Lead with a practical outcome."}),
        ("creator_package", {"title_options": ["One", "Two", "Three"]}),
        ("publishing_manifest", {"platforms": ["youtube", "instagram", "tiktok"]}),
        ("business_metrics", {"revenue": 175, "rpm": 7.5, "retention": 48}),
        ("mission_learning.lesson", {"observation": "Revenue pattern succeeded.", "score_influence": 4}),
    )
    for artifact_type, value in values:
        control.register_artifact(
            mission_id=mission_id, task_id=task_id,
            artifact_type=artifact_type,
            location=f"mission-control://{mission_id}/{artifact_type}",
            value=value, provenance={"offline": True},
        )
    control.repository.save_approval(ApprovalRequest(
        mission_id=mission_id, task_id=task_id,
        requested_action="approve_publishing_manifest", risk=RiskLevel.CONSEQUENTIAL,
        content_hash="a" * 64, expires_at=utc_now() + timedelta(hours=1),
    ))
    app = create_app(
        dashboard_service=result.dashboard_service,
        mission_control_service=control,
    )
    return TestClient(app), app, control, result


def test_home_renders_persisted_counts_and_capabilities(operations_context):
    client, _, _, result = operations_context
    response = client.get("/")
    assert response.status_code == 200
    for text in (
        "Total missions", "Active missions", "Pending approvals",
        "Creator packages", "Publishing manifests", "Recent lessons",
        "creator_package", "publishing_manifest", "business_metrics",
        "Revenue pattern succeeded.", "Score 0.00",
    ):
        assert text in response.text
    assert f"/missions/{result.mission_id}/review" in response.text


def test_mission_list_and_pipeline_use_canonical_state(operations_context):
    client, _, _, result = operations_context
    response = client.get("/missions")
    assert response.status_code == 200
    assert f"/missions/{result.mission_id}/review" in response.text
    for stage in (
        "Evidence", "Content Intelligence", "Mission Generation", "Production",
        "Founder Review", "Publishing Preparation", "Business Intelligence",
        "Mission Learning",
    ):
        assert stage in response.text
    assert "14/14 tasks complete" not in response.text
    assert "13/14 tasks complete" in response.text


def test_attention_activity_and_system_status_are_honest(operations_context):
    client, _, _, _ = operations_context
    text = client.get("/").text
    normalized = text.casefold()
    assert "approve_mission_zero_content" in text
    assert "Publishing manifest approval" in text
    assert "artifact.registered" in text
    for value in (
        "Mission Control", "Knowledge Manager", "Crawl4AI adapter",
        "Provider Router", "Publishing execution", "offline fallback",
        "unavailable", "disabled",
    ):
        assert value.casefold() in normalized
    assert "Gemini" not in text and "ElevenLabs" not in text and "HeyGen" not in text


def test_operations_v2_adds_no_mutation_route(operations_context):
    _, app, _, _ = operations_context
    mutation_paths = {
        path for path, methods in app.openapi()["paths"].items()
        if "post" in methods
    }
    assert mutation_paths == {"/missions/{mission_id}/review/decision"}


def test_projection_performs_no_external_operation(operations_context, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("External operation attempted.")

    monkeypatch.setattr("web_intelligence.service.WebIntelligenceService.execute", forbidden)
    monkeypatch.setattr("providers.gemini.transport.UnavailableGeminiTransport.send", forbidden)
    monkeypatch.setattr("private_video_production.render.service.PrivateRenderService.render", forbidden)
    client, _, _, _ = operations_context
    assert client.get("/").status_code == 200
    tracked = subprocess.run(
        ["git", "ls-files", "founder_inputs/mission_zero.json"], cwd=ROOT,
        capture_output=True, text=True, check=True,
    )
    assert tracked.stdout.strip() == ""
