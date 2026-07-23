"""Phase 4 Milestone 3 deterministic mission lesson tests."""

from __future__ import annotations

import inspect
import re
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.dashboard.operations_v2 import (
    DashboardMissionLesson,
    build_operations_projection,
)
from app.dashboard.service import DashboardService
from app.main import create_app
from app.runtime.mission_commands import MissionCommandService
from mission_control.mission_lessons import (
    LESSON_RULESET_VERSION,
    build_mission_lesson_payload,
    mission_lesson_payload_hash,
)
from mission_control.models import (
    AnalyticsMetrics,
    AnalyticsSnapshot,
    ConflictingDecisionError,
    DuplicateRecordError,
    InterpretationClassification,
    ItemNotFoundError,
    LessonCategory,
    LessonEvidenceState,
    MalformedCommandError,
    MissionLesson,
    MissionRecord,
    MismatchError,
    PublicationRecord,
    PublishingQueueItem,
    PublishingQueueStatus,
    RepositoryConsistencyError,
    RepositoryIntegrityError,
    StaleContentError,
)
from mission_control.repository import (
    InMemoryMissionControlRepository,
    MissionControlRepository,
    SQLiteMissionControlRepository,
)
from mission_control.service import MissionControlService


def _context(metrics: AnalyticsMetrics | None = None):
    repository = InMemoryMissionControlRepository()
    control = MissionControlService(repository)
    mission = MissionRecord(
        title="Learn from analytics",
        objective="Create evidence-backed mission knowledge.",
        founder_owner="Founder",
        publishing_generation=1,
    )
    queue = PublishingQueueItem(
        mission_id=mission.mission_id,
        manifest_id=uuid4(),
        source_package_id=uuid4(),
        target_platforms=["youtube"],
        destination="youtube",
        generation=1,
        manifest_hash="a" * 64,
        status=PublishingQueueStatus.PUBLISHED_CONFIRMED,
    )
    publication = PublicationRecord(
        mission_id=mission.mission_id,
        queue_item_id=queue.queue_item_id,
        destination=queue.destination,
        content_hash=queue.manifest_hash,
        published_by_actor="Founder",
    )
    snapshot = AnalyticsSnapshot(
        mission_id=mission.mission_id,
        publication_id=publication.publication_id,
        queue_item_id=queue.queue_item_id,
        destination=queue.destination,
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
        imported_at=datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
        imported_by_actor="Founder",
        payload_hash="b" * 64,
        metrics=metrics
        or AnalyticsMetrics(
            impressions=100,
            views=100,
            clicks=6,
            likes=3,
            comments=1,
            shares=1,
            saves=1,
        ),
    )
    repository.save_mission(mission)
    repository.save_publishing_queue_item(queue)
    repository.save_publication_record(publication)
    repository.save_analytics_snapshot(snapshot)
    interpretation = control.interpret_analytics_snapshot(
        mission_id=mission.mission_id,
        analytics_snapshot_id=snapshot.analytics_snapshot_id,
        interpreted_by_actor="Founder",
    )
    return (
        repository,
        control,
        mission,
        queue,
        publication,
        snapshot,
        interpretation,
    )


def _create(control, mission, interpretation):
    return control.create_mission_lesson(
        mission_id=mission.mission_id,
        analytics_interpretation_id=(
            interpretation.analytics_interpretation_id
        ),
        created_by_actor="Founder",
    )


def test_lesson_payload_is_deterministic_traceable_and_non_prescriptive():
    *_, interpretation = _context()
    first = build_mission_lesson_payload(interpretation)
    second = build_mission_lesson_payload(interpretation)

    assert first == second
    assert mission_lesson_payload_hash(first) == mission_lesson_payload_hash(
        second
    )
    assert first.evidence_references
    assert all(
        reference.analytics_interpretation_id
        == interpretation.analytics_interpretation_id
        for reference in first.evidence_references
    )
    serialized = first.model_dump_json().casefold()
    for forbidden in ("recommend", "should", "publish", "render", "execute"):
        assert forbidden not in serialized


def test_zero_and_missing_evidence_are_preserved_conservatively():
    *_, interpretation = _context(
        AnalyticsMetrics(impressions=0, views=0, clicks=0)
    )
    payload = build_mission_lesson_payload(interpretation)
    states = {
        reference.evidence_state for reference in payload.evidence_references
    }
    assert LessonEvidenceState.ZERO in states
    assert LessonEvidenceState.MISSING in states
    assert any(
        finding.category == LessonCategory.INSUFFICIENT_EVIDENCE
        for finding in payload.unknowns
    )
    assert interpretation.overall_classification == (
        InterpretationClassification.INSUFFICIENT_DATA
    )


def test_lesson_models_are_frozen_and_reject_unknown_fields():
    _, control, mission, _, _, _, interpretation = _context()
    lesson = _create(control, mission, interpretation)
    with pytest.raises(Exception):
        lesson.summary = "changed"
    with pytest.raises(ValueError):
        MissionLesson.model_validate(
            {**lesson.model_dump(), "unknown": True}
        )


def test_repository_contract_and_in_memory_persistence():
    for name in (
        "save_mission_lesson",
        "find_mission_lesson_by_id",
        "find_interpretation_ruleset_lesson",
        "list_mission_lessons",
    ):
        assert name in MissionControlRepository.__abstractmethods__

    repository, control, mission, _, publication, _, interpretation = (
        _context()
    )
    lesson = _create(control, mission, interpretation)
    assert repository.find_mission_lesson_by_id(
        lesson.mission_lesson_id
    ) == lesson
    assert repository.find_interpretation_ruleset_lesson(
        interpretation.analytics_interpretation_id,
        LESSON_RULESET_VERSION,
    ) == lesson
    assert repository.list_mission_lessons(
        publication.publication_id
    ) == [lesson]


def test_in_memory_duplicate_interpretation_ruleset_rejected():
    repository, control, mission, _, _, _, interpretation = _context()
    first = _create(control, mission, interpretation)
    with pytest.raises(DuplicateRecordError):
        repository.save_mission_lesson(
            first.model_copy(update={"mission_lesson_id": uuid4()})
        )


def test_sqlite_schema_and_exception_translation(tmp_path):
    repository = SQLiteMissionControlRepository(
        tmp_path / "mission-control.db",
        allowed_root=tmp_path,
    )
    assert repository.SCHEMA_VERSION == 6
    columns = {
        row[1]
        for row in repository.connection.execute(
            "PRAGMA table_info(mission_lessons)"
        )
    }
    assert {
        "analytics_interpretation_id",
        "lesson_ruleset_version",
        "payload_hash",
        "data",
    } <= columns


def test_schema_v3_migration_preserves_existing_records(tmp_path):
    path = tmp_path / "existing.db"
    repository = SQLiteMissionControlRepository(path, allowed_root=tmp_path)
    mission = MissionRecord(
        title="Existing mission",
        objective="Survive schema migration.",
        founder_owner="Founder",
    )
    repository.save_mission(mission)
    repository.connection.execute("DROP TABLE mission_lessons")
    repository.connection.execute(
        "UPDATE schema_version SET version = 3"
    )
    repository.connection.close()

    reopened = SQLiteMissionControlRepository(path, allowed_root=tmp_path)
    assert reopened.connection.execute(
        "SELECT version FROM schema_version"
    ).fetchone()[0] == 6
    assert reopened.get_mission(mission.mission_id) == mission
    assert reopened.connection.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type = 'table' AND name = 'mission_lessons'"
    ).fetchone()


def test_service_success_event_idempotency_and_source_immutability():
    repository, control, mission, _, publication, snapshot, interpretation = (
        _context()
    )
    source = (snapshot, interpretation, publication, mission)
    first = _create(control, mission, interpretation)
    second = _create(control, mission, interpretation)

    assert first == second
    events = [
        event
        for event in repository.list_events()
        if event.event_type == "analytics.lesson_created"
    ]
    assert len(events) == 1
    assert set(events[0].payload) == {
        "mission_lesson_id",
        "analytics_interpretation_id",
        "analytics_snapshot_id",
        "publication_id",
        "queue_item_id",
        "mission_id",
        "destination",
        "lesson_ruleset_version",
        "confidence",
        "created_at",
        "actor",
        "payload_hash",
    }
    assert repository.find_snapshot_by_id(
        snapshot.analytics_snapshot_id
    ) == source[0]
    assert repository.find_interpretation_by_id(
        interpretation.analytics_interpretation_id
    ) == source[1]
    assert repository.get_publication_record_by_id(
        publication.publication_id
    ) == source[2]
    assert repository.get_mission(mission.mission_id) == source[3]


def test_service_rejects_missing_invalid_actor_ruleset_and_stale_source():
    repository, control, mission, _, _, _, interpretation = _context()
    with pytest.raises(ItemNotFoundError):
        control.create_mission_lesson(
            mission_id=uuid4(),
            analytics_interpretation_id=(
                interpretation.analytics_interpretation_id
            ),
            created_by_actor="Founder",
        )
    with pytest.raises(ItemNotFoundError):
        control.create_mission_lesson(
            mission_id=mission.mission_id,
            analytics_interpretation_id=uuid4(),
            created_by_actor="Founder",
        )
    with pytest.raises(MalformedCommandError):
        control.create_mission_lesson(
            mission_id=mission.mission_id,
            analytics_interpretation_id=(
                interpretation.analytics_interpretation_id
            ),
            created_by_actor=" ",
        )
    with pytest.raises(MalformedCommandError):
        control.create_mission_lesson(
            mission_id=mission.mission_id,
            analytics_interpretation_id=(
                interpretation.analytics_interpretation_id
            ),
            created_by_actor="Founder",
            lesson_ruleset_version="unknown",
        )
    repository.analytics_interpretations[
        interpretation.analytics_interpretation_id
    ] = interpretation.model_copy(update={"payload_hash": "f" * 64})
    with pytest.raises(StaleContentError):
        _create(control, mission, interpretation)


def test_service_rejects_identity_mismatch():
    repository, control, mission, _, _, _, interpretation = _context()
    repository.analytics_interpretations[
        interpretation.analytics_interpretation_id
    ] = interpretation.model_copy(update={"destination": "tiktok"})
    with pytest.raises(MismatchError):
        _create(control, mission, interpretation)


def test_service_rejects_internally_inconsistent_interpretation():
    repository, control, mission, _, _, _, interpretation = _context()
    repository.analytics_interpretations[
        interpretation.analytics_interpretation_id
    ] = interpretation.model_copy(update={"summary": "Tampered summary."})
    with pytest.raises(StaleContentError):
        _create(control, mission, interpretation)


def _collision(monkeypatch, repository, winner):
    lookups = iter((None, winner))
    monkeypatch.setattr(
        repository,
        "find_interpretation_ruleset_lesson",
        lambda *_: next(lookups),
    )
    monkeypatch.setattr(
        repository,
        "save_mission_lesson",
        lambda *_: (_ for _ in ()).throw(DuplicateRecordError("collision")),
    )
    events = []
    monkeypatch.setattr(repository, "append_event", events.append)
    return events


def test_concurrent_collision_paths_fail_closed(monkeypatch):
    repository, control, mission, _, _, _, interpretation = _context()
    payload = build_mission_lesson_payload(interpretation)
    winner = MissionLesson(
        mission_id=mission.mission_id,
        publication_id=interpretation.publication_id,
        queue_item_id=interpretation.queue_item_id,
        analytics_snapshot_id=interpretation.analytics_snapshot_id,
        analytics_interpretation_id=(
            interpretation.analytics_interpretation_id
        ),
        destination=interpretation.destination,
        lesson_ruleset_version=LESSON_RULESET_VERSION,
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
        created_by_actor="Founder",
        payload_hash=mission_lesson_payload_hash(payload),
        confidence=payload.confidence,
        summary=payload.summary,
        findings=payload.findings,
        evidence_references=payload.evidence_references,
        strengths=payload.strengths,
        weaknesses=payload.weaknesses,
        unknowns=payload.unknowns,
    )
    events = _collision(monkeypatch, repository, winner)
    assert _create(control, mission, interpretation) == winner
    assert events == []

    repository, control, mission, _, _, _, interpretation = _context()
    _collision(
        monkeypatch,
        repository,
        winner.model_copy(update={"payload_hash": "f" * 64}),
    )
    with pytest.raises(ConflictingDecisionError):
        _create(control, mission, interpretation)

    repository, control, mission, _, _, _, interpretation = _context()
    _collision(monkeypatch, repository, None)
    with pytest.raises(RepositoryConsistencyError):
        _create(control, mission, interpretation)


def test_command_delegates_without_accepting_derived_output():
    _, control, mission, _, _, _, interpretation = _context()
    command = MissionCommandService(SimpleNamespace(mission_control=control))
    result = command.create_mission_lesson(
        mission_id=mission.mission_id,
        analytics_interpretation_id=(
            interpretation.analytics_interpretation_id
        ),
        actor="Local Founder",
    )
    assert isinstance(result, MissionLesson)
    signature = inspect.signature(command.create_mission_lesson)
    for forbidden in ("confidence", "summary", "findings", "evidence"):
        assert forbidden not in signature.parameters


@pytest.fixture()
def route_context():
    repository, control, mission, queue, publication, snapshot, interpretation = (
        _context()
    )
    runtime = SimpleNamespace(mission_control=control)
    app = create_app(
        dashboard_service=DashboardService(mission_control_service=control),
        mission_control_service=control,
        runtime_manager=runtime,
        mission_command_service=MissionCommandService(runtime),
    )
    return (
        TestClient(app),
        control,
        mission,
        queue,
        publication,
        snapshot,
        interpretation,
    )


def _lesson_path(mission, interpretation):
    return (
        f"/missions/{mission.mission_id}/analytics/interpretations/"
        f"{interpretation.analytics_interpretation_id}/lesson"
    )


def test_get_and_post_render_durable_lesson(route_context):
    client, _, mission, _, _, _, interpretation = route_context
    page = client.get(_lesson_path(mission, interpretation))
    token = re.search(
        r'name="csrf_token" value="([^"]+)"',
        page.text,
    ).group(1)
    assert page.status_code == 200
    assert str(interpretation.analytics_interpretation_id) in page.text

    response = client.post(
        _lesson_path(mission, interpretation),
        data={"csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 303
    rendered = client.get(_lesson_path(mission, interpretation))
    assert LESSON_RULESET_VERSION in rendered.text
    assert "Evidence provenance" in rendered.text
    assert "Payload hash" in rendered.text


@pytest.mark.parametrize(
    "body",
    [
        b"",
        b"csrf_token=" + b"x" * 32,
        b"csrf_token=" + b"x" * 32 + b"&csrf_token=" + b"y" * 32,
        b"csrf_token=" + b"x" * 32 + b"&summary=injected",
    ],
)
def test_post_rejects_csrf_repetition_and_derived_fields(
    route_context,
    body,
):
    client, _, mission, _, _, _, interpretation = route_context
    client.get(_lesson_path(mission, interpretation))
    response = client.post(
        _lesson_path(mission, interpretation),
        content=body,
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code in {403, 422}


def test_post_body_size_and_local_boundary(route_context):
    client, _, mission, _, _, _, interpretation = route_context
    path = _lesson_path(mission, interpretation)
    assert client.post(
        path,
        content=b"csrf_token=" + b"x" * 13_000,
        headers={"content-type": "application/x-www-form-urlencoded"},
    ).status_code == 413
    remote = TestClient(client.app, client=("remote.example", 50_000))
    assert remote.post(
        path,
        content=b"csrf_token=" + b"x" * 32,
        headers={"content-type": "application/x-www-form-urlencoded"},
    ).status_code == 403


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (ItemNotFoundError("missing"), 404),
        (MismatchError("mismatch"), 422),
        (MalformedCommandError("malformed"), 422),
        (ConflictingDecisionError("conflict"), 409),
        (StaleContentError("stale"), 409),
        (RepositoryIntegrityError("database details"), 503),
        (RepositoryConsistencyError("consistency details"), 503),
    ],
)
def test_post_maps_errors_without_internal_details(
    route_context,
    monkeypatch,
    error,
    status,
):
    client, _, mission, _, _, _, interpretation = route_context
    path = _lesson_path(mission, interpretation)
    page = client.get(path)
    token = re.search(
        r'name="csrf_token" value="([^"]+)"',
        page.text,
    ).group(1)

    def fail(**_values):
        raise error

    monkeypatch.setattr(
        client.app.state.mission_command_service,
        "create_mission_lesson",
        fail,
    )
    response = client.post(path, data={"csrf_token": token})
    assert response.status_code == status
    if status == 503:
        assert "database details" not in response.text
        assert "consistency details" not in response.text


def test_get_missing_and_mismatch_paths_are_safe(route_context):
    client, control, mission, _, _, _, interpretation = route_context
    assert client.get(
        _lesson_path(
            MissionRecord(
                title="Missing",
                objective="Missing",
                founder_owner="Founder",
            ),
            interpretation,
        )
    ).status_code == 404
    assert client.get(
        f"/missions/{mission.mission_id}/analytics/interpretations/"
        f"{uuid4()}/lesson"
    ).status_code == 404
    other = MissionRecord(
        title="Other",
        objective="Other",
        founder_owner="Founder",
    )
    control.repository.save_mission(other)
    assert client.get(
        _lesson_path(other, interpretation)
    ).status_code == 422


def test_dashboard_projection_empty_then_typed_lesson(route_context):
    _, control, mission, _, _, _, interpretation = route_context
    before = build_operations_projection(control).publishing_queue[0]
    assert isinstance(
        before.analytics.interpretation.lesson,
        DashboardMissionLesson,
    )
    assert before.analytics.interpretation.lesson.lesson_count == 0
    assert before.analytics.interpretation.lesson.lesson_actionable is True

    created = _create(control, mission, interpretation)
    lesson_view = (
        build_operations_projection(control)
        .publishing_queue[0]
        .analytics.interpretation.lesson
    )
    assert lesson_view.latest_lesson == created
    assert lesson_view.lesson_count == 1
    assert lesson_view.lesson_actionable is False
    assert "already exists" in lesson_view.lesson_blocking_reason


def test_service_and_command_have_no_sqlite_or_external_dependencies():
    source = (
        inspect.getsource(MissionControlService.create_mission_lesson)
        + inspect.getsource(MissionCommandService.create_mission_lesson)
    ).casefold()
    for forbidden in (
        "sqlite3",
        "requests.",
        "playwright",
        "selenium",
        "publish(",
        "render(",
    ):
        assert forbidden not in source
