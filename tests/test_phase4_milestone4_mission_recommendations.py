"""Phase 4 Milestone 4 founder-reviewed recommendation tests."""
from __future__ import annotations

import inspect
import re
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.dashboard.operations_v2 import (
    DashboardMissionRecommendation,
    build_operations_projection,
)
from app.dashboard.service import DashboardService
from app.main import create_app
from app.runtime.mission_commands import MissionCommandService
from mission_control.mission_recommendations import (
    RECOMMENDATION_RULESET_VERSION,
    build_mission_recommendation_payload,
    mission_recommendation_payload_hash,
)
from mission_control.models import (
    ConflictingDecisionError,
    DuplicateRecordError,
    ItemNotFoundError,
    MalformedCommandError,
    MissionRecommendation,
    MissionRecord,
    MismatchError,
    RecommendationCategory,
    RecommendationDecision,
    RecommendationStatus,
    RepositoryConsistencyError,
    RepositoryIntegrityError,
)
from mission_control.repository import (
    MissionControlRepository,
    SQLiteMissionControlRepository,
)
from test_phase4_milestone3_mission_lessons import _context, _create


def _recommendation_context():
    values = _context()
    repository, control, mission, _, _, _, interpretation = values
    lesson = _create(control, mission, interpretation)
    return (*values, lesson)


def _create_recommendation(control, mission, lesson):
    return control.create_mission_recommendation(
        mission_id=mission.mission_id,
        mission_lesson_id=lesson.mission_lesson_id,
        created_by_actor="Founder",
    )


def test_engine_is_deterministic_advisory_and_traceable():
    *_, lesson = _recommendation_context()
    first = build_mission_recommendation_payload(lesson)
    second = build_mission_recommendation_payload(lesson)
    assert first == second
    assert mission_recommendation_payload_hash(first) == (
        mission_recommendation_payload_hash(second)
    )
    assert first.proposals
    assert first.evidence_references
    text = first.model_dump_json().casefold()
    for forbidden in (
        "create mission",
        "publish another",
        "guarantee",
        "automatically",
        "execute work",
    ):
        assert forbidden not in text


def test_mixed_lesson_preserves_strengths_and_unknowns():
    *_, lesson = _recommendation_context()
    payload = build_mission_recommendation_payload(lesson)
    categories = {item.category for item in payload.proposals}
    assert RecommendationCategory.PRESERVE_STRENGTH in categories
    assert RecommendationCategory.COLLECT_MORE_EVIDENCE in categories


def test_no_supported_finding_produces_no_actionable_state():
    *_, lesson = _recommendation_context()
    empty = lesson.model_copy(update={
        "findings": (),
        "strengths": (),
        "weaknesses": (),
        "unknowns": (),
    })
    payload = build_mission_recommendation_payload(empty)
    assert len(payload.proposals) == 1
    assert payload.proposals[0].category == (
        RecommendationCategory.NO_ACTIONABLE_RECOMMENDATION
    )


def test_model_is_immutable_rejects_extra_and_hash_excludes_review_state():
    _, control, mission, _, _, _, _, lesson = _recommendation_context()
    recommendation = _create_recommendation(control, mission, lesson)
    with pytest.raises(Exception):
        recommendation.status = RecommendationStatus.ACCEPTED
    with pytest.raises(ValueError):
        MissionRecommendation.model_validate(
            {**recommendation.model_dump(), "extra": True}
        )
    payload = build_mission_recommendation_payload(lesson)
    before = mission_recommendation_payload_hash(payload)
    reviewed = recommendation.model_copy(update={
        "status": RecommendationStatus.ACCEPTED,
        "decided_by": "Another founder",
    })
    assert reviewed.payload_hash == before


def test_repository_contract_and_in_memory_identity():
    for name in (
        "save_mission_recommendation",
        "update_mission_recommendation",
        "find_mission_recommendation_by_id",
        "find_lesson_ruleset_recommendation",
        "list_mission_recommendations",
    ):
        assert name in MissionControlRepository.__abstractmethods__
    repository, control, mission, _, publication, _, _, lesson = (
        _recommendation_context()
    )
    value = _create_recommendation(control, mission, lesson)
    assert repository.find_mission_recommendation_by_id(
        value.mission_recommendation_id
    ) == value
    assert repository.list_mission_recommendations(
        publication.publication_id
    ) == [value]
    with pytest.raises(DuplicateRecordError):
        repository.save_mission_recommendation(
            value.model_copy(update={"mission_recommendation_id": uuid4()})
        )


def test_sqlite_schema_v5_and_v4_migration(tmp_path):
    path = tmp_path / "control.db"
    repository = SQLiteMissionControlRepository(path, allowed_root=tmp_path)
    assert repository.SCHEMA_VERSION == 5
    assert {
        "mission_lesson_id",
        "recommendation_ruleset_version",
        "status",
        "data",
    } <= {
        row[1]
        for row in repository.connection.execute(
            "PRAGMA table_info(mission_recommendations)"
        )
    }
    mission = MissionRecord(
        title="Existing", objective="Preserve", founder_owner="Founder"
    )
    repository.save_mission(mission)
    repository.connection.execute("DROP TABLE mission_recommendations")
    repository.connection.execute("UPDATE schema_version SET version = 4")
    repository.connection.close()
    reopened = SQLiteMissionControlRepository(path, allowed_root=tmp_path)
    assert reopened.get_mission(mission.mission_id) == mission
    assert reopened.connection.execute(
        "SELECT version FROM schema_version"
    ).fetchone()[0] == 5


def test_creation_success_idempotency_event_and_source_immutability():
    repository, control, mission, queue, publication, snapshot, interpretation, lesson = (
        _recommendation_context()
    )
    originals = (mission, queue, publication, snapshot, interpretation, lesson)
    first = _create_recommendation(control, mission, lesson)
    second = _create_recommendation(control, mission, lesson)
    assert first == second
    events = [
        item for item in repository.list_events()
        if item.event_type == "analytics.recommendation_created"
    ]
    assert len(events) == 1
    assert repository.get_mission(mission.mission_id) == originals[0]
    assert repository.get_publishing_queue_item(queue.queue_item_id) == originals[1]
    assert repository.find_mission_lesson_by_id(lesson.mission_lesson_id) == originals[5]


def test_creation_validation_and_conflicting_existing_payload():
    repository, control, mission, _, _, _, _, lesson = _recommendation_context()
    with pytest.raises(ItemNotFoundError):
        control.create_mission_recommendation(
            mission_id=uuid4(), mission_lesson_id=lesson.mission_lesson_id,
            created_by_actor="Founder",
        )
    with pytest.raises(ItemNotFoundError):
        control.create_mission_recommendation(
            mission_id=mission.mission_id, mission_lesson_id=uuid4(),
            created_by_actor="Founder",
        )
    with pytest.raises(MalformedCommandError):
        control.create_mission_recommendation(
            mission_id=mission.mission_id,
            mission_lesson_id=lesson.mission_lesson_id,
            created_by_actor=" ",
        )
    value = _create_recommendation(control, mission, lesson)
    repository.mission_recommendations[value.mission_recommendation_id] = (
        value.model_copy(update={"payload_hash": "f" * 64})
    )
    with pytest.raises(ConflictingDecisionError):
        _create_recommendation(control, mission, lesson)


def test_creation_mismatch_fails_closed():
    repository, control, mission, _, _, _, _, lesson = _recommendation_context()
    repository.mission_lessons[lesson.mission_lesson_id] = lesson.model_copy(
        update={"destination": "tiktok"}
    )
    with pytest.raises(MismatchError):
        _create_recommendation(control, mission, lesson)


def test_creation_collision_recovery(monkeypatch):
    repository, control, mission, _, _, _, _, lesson = _recommendation_context()
    winner = _create_recommendation(control, mission, lesson)
    repository.mission_recommendations.clear()
    lookups = iter((None, winner))
    monkeypatch.setattr(
        repository, "find_lesson_ruleset_recommendation",
        lambda *_: next(lookups),
    )
    monkeypatch.setattr(
        repository, "save_mission_recommendation",
        lambda *_: (_ for _ in ()).throw(DuplicateRecordError("collision")),
    )
    events = []
    monkeypatch.setattr(repository, "append_event", events.append)
    assert _create_recommendation(control, mission, lesson) == winner
    assert events == []


@pytest.mark.parametrize(
    ("decision", "status"),
    [
        (RecommendationDecision.ACCEPT, RecommendationStatus.ACCEPTED),
        (RecommendationDecision.REJECT, RecommendationStatus.REJECTED),
    ],
)
def test_founder_review_is_final_idempotent_and_non_executing(decision, status):
    repository, control, mission, _, _, _, _, lesson = _recommendation_context()
    before = mission.model_copy(deep=True)
    recommendation = _create_recommendation(control, mission, lesson)
    first = control.review_mission_recommendation(
        mission_id=mission.mission_id,
        mission_recommendation_id=recommendation.mission_recommendation_id,
        decision=decision,
        decided_by_actor="Founder",
        founder_note="Reviewed.",
    )
    second = control.review_mission_recommendation(
        mission_id=mission.mission_id,
        mission_recommendation_id=recommendation.mission_recommendation_id,
        decision=decision,
        decided_by_actor="Founder",
        founder_note=" Reviewed. ",
    )
    assert first == second
    assert first.status == status
    assert repository.get_mission(mission.mission_id) == before
    assert len([
        event for event in repository.list_events()
        if event.event_type == "analytics.recommendation_reviewed"
    ]) == 1


def test_conflicting_review_fails_closed():
    _, control, mission, _, _, _, _, lesson = _recommendation_context()
    value = _create_recommendation(control, mission, lesson)
    control.review_mission_recommendation(
        mission_id=mission.mission_id,
        mission_recommendation_id=value.mission_recommendation_id,
        decision=RecommendationDecision.ACCEPT,
        decided_by_actor="Founder",
    )
    with pytest.raises(ConflictingDecisionError):
        control.review_mission_recommendation(
            mission_id=mission.mission_id,
            mission_recommendation_id=value.mission_recommendation_id,
            decision=RecommendationDecision.REJECT,
            decided_by_actor="Founder",
        )


def test_command_signatures_reject_generated_content():
    _, control, mission, _, _, _, _, lesson = _recommendation_context()
    command = MissionCommandService(SimpleNamespace(mission_control=control))
    value = command.create_mission_recommendation(
        mission_id=mission.mission_id,
        mission_lesson_id=lesson.mission_lesson_id,
        actor="Local Founder",
    )
    assert isinstance(value, MissionRecommendation)
    signature = inspect.signature(command.create_mission_recommendation)
    for forbidden in ("summary", "proposals", "rationale", "confidence"):
        assert forbidden not in signature.parameters


@pytest.fixture()
def route_context():
    repository, control, mission, queue, publication, snapshot, interpretation, lesson = (
        _recommendation_context()
    )
    runtime = SimpleNamespace(mission_control=control)
    app = create_app(
        dashboard_service=DashboardService(mission_control_service=control),
        mission_control_service=control,
        runtime_manager=runtime,
        mission_command_service=MissionCommandService(runtime),
    )
    return TestClient(app), control, mission, lesson


def _path(mission, lesson):
    return (
        f"/missions/{mission.mission_id}/lessons/"
        f"{lesson.mission_lesson_id}/recommendation"
    )


def test_route_create_accept_and_render(route_context):
    client, _, mission, lesson = route_context
    page = client.get(_path(mission, lesson))
    token = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
    assert page.status_code == 200
    response = client.post(
        _path(mission, lesson), data={"csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 303
    page = client.get(_path(mission, lesson))
    assert RECOMMENDATION_RULESET_VERSION in page.text
    assert "Advisory proposals" in page.text
    recommendation_id = re.search(
        r"/recommendations/([^/]+)/accept", page.text
    ).group(1)
    token = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
    response = client.post(
        f"/missions/{mission.mission_id}/recommendations/"
        f"{recommendation_id}/accept",
        data={"csrf_token": token, "founder_note": "Reviewed"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "Accepted" in client.get(_path(mission, lesson)).text


def test_routes_reject_csrf_unknown_fields_and_remote(route_context):
    client, _, mission, lesson = route_context
    path = _path(mission, lesson)
    client.get(path)
    assert client.post(path, data={"csrf_token": "x" * 32}).status_code == 403
    token = client.cookies["auraai_csrf"]
    assert client.post(
        path, data={"csrf_token": token, "summary": "injected"}
    ).status_code == 422
    remote = TestClient(client.app, client=("remote.example", 50000))
    assert remote.post(path, data={"csrf_token": token}).status_code == 403


def test_dashboard_projection_is_typed_and_non_generating(route_context):
    _, control, mission, lesson = route_context
    before = (
        build_operations_projection(control).publishing_queue[0]
        .analytics.interpretation.lesson.recommendation
    )
    assert isinstance(before, DashboardMissionRecommendation)
    assert before.creation_actionable is True
    value = _create_recommendation(control, mission, lesson)
    after = (
        build_operations_projection(control).publishing_queue[0]
        .analytics.interpretation.lesson.recommendation
    )
    assert after.latest_recommendation == value
    assert after.review_actionable is True
    assert after.creation_actionable is False


def test_service_has_no_sqlite_or_external_dependency():
    import mission_control.service as service_module

    source = inspect.getsource(service_module)
    assert "sqlite3" not in source
    for forbidden in ("playwright", "requests.", "selenium"):
        assert forbidden not in inspect.getsource(
            service_module.MissionControlService.create_mission_recommendation
        ).casefold()
