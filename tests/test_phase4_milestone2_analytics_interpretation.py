"""Phase 4 Milestone 2 deterministic analytics interpretation tests."""

from __future__ import annotations

import inspect
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.dashboard.operations_v2 import (
    DashboardAnalyticsInterpretation,
    build_operations_projection,
)
from app.dashboard.service import DashboardService
from app.main import create_app
from app.runtime.mission_commands import MissionCommandService
from core import utc_now
from mission_control.analytics_interpretation import (
    RULESET_VERSION,
    build_interpretation_payload,
    interpretation_payload_hash,
)
from mission_control.models import (
    AnalyticsInterpretation,
    AnalyticsMetrics,
    AnalyticsSnapshot,
    ConflictingDecisionError,
    DuplicateRecordError,
    InterpretationClassification,
    InterpretationConfidence,
    ItemNotFoundError,
    MalformedCommandError,
    MetricEvidenceState,
    MismatchError,
    MissionRecord,
    PublicationRecord,
    PublishingQueueItem,
    PublishingQueueStatus,
    RepositoryConsistencyError,
    RepositoryIntegrityError,
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
        title="Interpret analytics",
        objective="Interpret durable analytics evidence.",
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
        metrics=metrics or AnalyticsMetrics(
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
    return repository, control, mission, queue, publication, snapshot


def _interpretation(snapshot, *, interpreted_at=None, payload_hash="c" * 64):
    payload = build_interpretation_payload(snapshot)
    return AnalyticsInterpretation(
        mission_id=snapshot.mission_id,
        publication_id=snapshot.publication_id,
        queue_item_id=snapshot.queue_item_id,
        analytics_snapshot_id=snapshot.analytics_snapshot_id,
        destination=snapshot.destination,
        interpreted_at=interpreted_at or utc_now(),
        interpreted_by_actor="Founder",
        ruleset_version=RULESET_VERSION,
        overall_classification=payload.overall_classification,
        confidence=payload.confidence,
        metric_interpretations=payload.metric_interpretations,
        strengths=payload.strengths,
        weaknesses=payload.weaknesses,
        missing_evidence=payload.missing_evidence,
        summary=payload.summary,
        payload_hash=payload_hash,
    )


def test_interpretation_models_are_frozen_and_reject_unknown_fields():
    _, _, _, _, _, snapshot = _context()
    value = _interpretation(snapshot)
    with pytest.raises(Exception):
        value.summary = "changed"
    with pytest.raises(ValueError):
        AnalyticsInterpretation.model_validate(
            {**value.model_dump(), "unknown": True}
        )


def test_evidence_states_distinguish_zero_missing_and_available():
    metrics = AnalyticsMetrics(views=0, clicks=0)
    _, _, _, _, _, snapshot = _context(metrics)
    payload = build_interpretation_payload(snapshot)
    by_name = {item.metric_name: item for item in payload.metric_interpretations}

    assert by_name["views"].evidence_state == MetricEvidenceState.ZERO
    assert by_name["clicks"].evidence_state == MetricEvidenceState.ZERO
    assert by_name["impressions"].evidence_state == MetricEvidenceState.MISSING
    assert (
        by_name["engagement_rate"].evidence_state
        == MetricEvidenceState.MISSING
    )


def test_zero_denominator_is_not_applicable_and_never_divides():
    _, _, _, _, _, snapshot = _context(
        AnalyticsMetrics(impressions=0, clicks=0)
    )
    payload = build_interpretation_payload(snapshot)
    ctr = next(
        item
        for item in payload.metric_interpretations
        if item.metric_name == "click_through_rate"
    )
    assert ctr.evidence_state == MetricEvidenceState.NOT_APPLICABLE
    assert ctr.classification == InterpretationClassification.INSUFFICIENT_DATA


def test_deterministic_ratio_rounding_classification_and_explanation():
    _, _, _, _, _, snapshot = _context(
        AnalyticsMetrics(impressions=3, clicks=1)
    )
    first = build_interpretation_payload(snapshot)
    second = build_interpretation_payload(snapshot)
    ctr = first.metric_interpretations[-2]

    assert first == second
    assert ctr.normalized_value == "0.3333"
    assert ctr.classification == InterpretationClassification.OUTSTANDING
    assert RULESET_VERSION in ctr.explanation
    assert first.confidence == InterpretationConfidence.HIGH


def test_sparse_raw_totals_are_insufficient_with_low_confidence():
    _, _, _, _, _, snapshot = _context(AnalyticsMetrics(views=12))
    payload = build_interpretation_payload(snapshot)
    assert (
        payload.overall_classification
        == InterpretationClassification.INSUFFICIENT_DATA
    )
    assert payload.confidence == InterpretationConfidence.LOW


def test_equivalent_decimal_and_interpreted_time_do_not_change_hash():
    _, _, _, _, _, snapshot = _context(
        AnalyticsMetrics(
            views=1,
            revenue_amount=Decimal("10.50"),
            revenue_currency="USD",
        )
    )
    equivalent = snapshot.model_copy(
        update={
            "metrics": AnalyticsMetrics(
                views=1,
                revenue_amount=Decimal("10.5"),
                revenue_currency="USD",
            )
        }
    )
    first = build_interpretation_payload(snapshot)
    second = build_interpretation_payload(equivalent)
    assert interpretation_payload_hash(first) == interpretation_payload_hash(
        second
    )
    assert "interpreted_at" not in first.model_dump()


def test_findings_are_rule_traceable_and_never_recommend():
    _, _, _, _, _, snapshot = _context()
    payload = build_interpretation_payload(snapshot)
    findings = payload.strengths + payload.weaknesses + payload.missing_evidence
    assert findings
    assert all(item.rule_id.startswith(RULESET_VERSION) for item in findings)
    serialized = payload.model_dump_json().casefold()
    for forbidden in ("recommend", "should", "change the", "create shorter"):
        assert forbidden not in serialized


def test_repository_contract_contains_interpretation_methods():
    for name in (
        "save_analytics_interpretation",
        "find_interpretation_by_id",
        "find_snapshot_ruleset_interpretation",
        "list_analytics_interpretations",
    ):
        assert name in MissionControlRepository.__abstractmethods__


def test_in_memory_interpretation_persistence_order_and_defensive_copy():
    repository, _, _, _, _, snapshot = _context()
    older = _interpretation(
        snapshot,
        interpreted_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    newer_snapshot = snapshot.model_copy(
        update={"analytics_snapshot_id": uuid4()}
    )
    newer = _interpretation(
        newer_snapshot,
        interpreted_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    repository.save_analytics_interpretation(older)
    repository.save_analytics_interpretation(newer)

    assert repository.find_interpretation_by_id(
        older.analytics_interpretation_id
    ) == older
    assert repository.list_analytics_interpretations(
        snapshot.publication_id
    ) == [newer, older]


def test_in_memory_duplicate_snapshot_ruleset_rejected():
    repository, _, _, _, _, snapshot = _context()
    first = _interpretation(snapshot)
    repository.save_analytics_interpretation(first)
    with pytest.raises(DuplicateRecordError):
        repository.save_analytics_interpretation(
            first.model_copy(update={"analytics_interpretation_id": uuid4()})
        )


def test_sqlite_schema_migration_and_exception_translation(tmp_path):
    path = tmp_path / "mission-control.db"
    repository = SQLiteMissionControlRepository(path, allowed_root=tmp_path)
    assert repository.SCHEMA_VERSION == 6
    columns = {
        row[1]
        for row in repository.connection.execute(
            "PRAGMA table_info(analytics_interpretations)"
        )
    }
    assert {
        "analytics_snapshot_id",
        "ruleset_version",
        "payload_hash",
        "data",
    } <= columns
    repository.connection.execute("PRAGMA foreign_keys = OFF")
    _, _, _, _, _, snapshot = _context()
    first = _interpretation(snapshot)
    repository.save_analytics_interpretation(first)
    with pytest.raises(DuplicateRecordError):
        repository.save_analytics_interpretation(
            first.model_copy(update={"analytics_interpretation_id": uuid4()})
        )
    repository.connection.execute("PRAGMA foreign_keys = ON")
    with pytest.raises(RepositoryIntegrityError):
        repository.save_analytics_interpretation(
            first.model_copy(
                update={
                    "analytics_interpretation_id": uuid4(),
                    "analytics_snapshot_id": uuid4(),
                    "ruleset_version": "another-ruleset",
                }
            )
        )


def test_schema_v2_database_upgrades_without_rebuilding_analytics(tmp_path):
    path = tmp_path / "existing.db"
    repository = SQLiteMissionControlRepository(path, allowed_root=tmp_path)
    repository.connection.execute("UPDATE schema_version SET version = 2")
    repository.connection.close()

    reopened = SQLiteMissionControlRepository(path, allowed_root=tmp_path)
    version = reopened.connection.execute(
        "SELECT version FROM schema_version"
    ).fetchone()[0]
    assert version == 6


def test_service_success_event_idempotency_and_source_immutability():
    repository, control, mission, queue, publication, snapshot = _context()
    original = (
        snapshot.model_copy(deep=True),
        publication.model_copy(deep=True),
        queue.model_copy(deep=True),
        mission.model_copy(deep=True),
    )
    first = control.interpret_analytics_snapshot(
        mission_id=mission.mission_id,
        analytics_snapshot_id=snapshot.analytics_snapshot_id,
        interpreted_by_actor="Founder",
    )
    second = control.interpret_analytics_snapshot(
        mission_id=mission.mission_id,
        analytics_snapshot_id=snapshot.analytics_snapshot_id,
        interpreted_by_actor="Founder",
    )

    assert first == second
    events = [
        event
        for event in repository.list_events()
        if event.event_type == "analytics.interpreted"
    ]
    assert len(events) == 1
    assert set(events[0].payload) == {
        "analytics_interpretation_id",
        "analytics_snapshot_id",
        "mission_id",
        "publication_id",
        "queue_item_id",
        "destination",
        "ruleset_version",
        "overall_classification",
        "confidence",
        "interpreted_at",
        "actor",
        "payload_hash",
    }
    assert repository.find_snapshot_by_id(snapshot.analytics_snapshot_id) == original[0]
    assert repository.get_publication_record_by_id(publication.publication_id) == original[1]
    assert repository.get_publishing_queue_item(queue.queue_item_id) == original[2]
    assert repository.get_mission(mission.mission_id) == original[3]


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("snapshot_mission", "snapshot mission"),
        ("publication_mission", "Publication record mission"),
        ("queue_mission", "queue item mission"),
        ("destination", "destination"),
        ("content", "content identity"),
    ],
)
def test_service_rejects_identity_mismatches(mutation, message):
    repository, control, mission, queue, publication, snapshot = _context()
    if mutation == "snapshot_mission":
        repository.analytics_snapshots[snapshot.analytics_snapshot_id] = (
            snapshot.model_copy(update={"mission_id": uuid4()})
        )
    elif mutation == "publication_mission":
        repository.publication_records[publication.queue_item_id] = (
            publication.model_copy(update={"mission_id": uuid4()})
        )
    elif mutation == "queue_mission":
        repository.publishing_queue[queue.queue_item_id] = queue.model_copy(
            update={"mission_id": uuid4()}
        )
    elif mutation == "destination":
        repository.analytics_snapshots[snapshot.analytics_snapshot_id] = (
            snapshot.model_copy(update={"destination": "tiktok"})
        )
    else:
        repository.publication_records[publication.queue_item_id] = (
            publication.model_copy(update={"content_hash": "d" * 64})
        )
    with pytest.raises(MismatchError, match=message):
        control.interpret_analytics_snapshot(
            mission_id=mission.mission_id,
            analytics_snapshot_id=snapshot.analytics_snapshot_id,
            interpreted_by_actor="Founder",
        )


def test_service_missing_and_unsupported_ruleset_errors():
    _, control, mission, _, _, snapshot = _context()
    with pytest.raises(ItemNotFoundError):
        control.interpret_analytics_snapshot(
            mission_id=uuid4(),
            analytics_snapshot_id=snapshot.analytics_snapshot_id,
            interpreted_by_actor="Founder",
        )
    with pytest.raises(ItemNotFoundError):
        control.interpret_analytics_snapshot(
            mission_id=mission.mission_id,
            analytics_snapshot_id=uuid4(),
            interpreted_by_actor="Founder",
        )
    with pytest.raises(MalformedCommandError):
        control.interpret_analytics_snapshot(
            mission_id=mission.mission_id,
            analytics_snapshot_id=snapshot.analytics_snapshot_id,
            interpreted_by_actor="Founder",
            ruleset_version="unknown",
        )


def _collision(monkeypatch, repository, winner):
    lookups = iter((None, winner))
    monkeypatch.setattr(
        repository,
        "find_snapshot_ruleset_interpretation",
        lambda *_: next(lookups),
    )
    monkeypatch.setattr(
        repository,
        "save_analytics_interpretation",
        lambda *_: (_ for _ in ()).throw(DuplicateRecordError("collision")),
    )
    events = []
    monkeypatch.setattr(repository, "append_event", events.append)
    return events


def test_concurrent_identical_collision_returns_winner_without_event(monkeypatch):
    repository, control, mission, _, _, snapshot = _context()
    payload = build_interpretation_payload(snapshot)
    winner = _interpretation(
        snapshot,
        payload_hash=interpretation_payload_hash(payload),
    )
    events = _collision(monkeypatch, repository, winner)
    result = control.interpret_analytics_snapshot(
        mission_id=mission.mission_id,
        analytics_snapshot_id=snapshot.analytics_snapshot_id,
        interpreted_by_actor="Founder",
    )
    assert result == winner
    assert events == []


def test_concurrent_conflict_and_missing_winner_fail_closed(monkeypatch):
    repository, control, mission, _, _, snapshot = _context()
    conflict = _interpretation(snapshot, payload_hash="f" * 64)
    _collision(monkeypatch, repository, conflict)
    with pytest.raises(ConflictingDecisionError):
        control.interpret_analytics_snapshot(
            mission_id=mission.mission_id,
            analytics_snapshot_id=snapshot.analytics_snapshot_id,
            interpreted_by_actor="Founder",
        )

    repository, control, mission, _, _, snapshot = _context()
    _collision(monkeypatch, repository, None)
    with pytest.raises(RepositoryConsistencyError):
        control.interpret_analytics_snapshot(
            mission_id=mission.mission_id,
            analytics_snapshot_id=snapshot.analytics_snapshot_id,
            interpreted_by_actor="Founder",
        )


def test_service_has_no_sqlite_dependency():
    import mission_control.service as service_module

    assert "sqlite3" not in inspect.getsource(service_module)


def test_command_delegates_without_accepting_interpretation_output():
    _, control, mission, _, _, snapshot = _context()
    runtime = SimpleNamespace(mission_control=control)
    command = MissionCommandService(runtime)

    result = command.interpret_analytics_snapshot(
        mission_id=mission.mission_id,
        analytics_snapshot_id=snapshot.analytics_snapshot_id,
        actor="Local Founder",
    )

    assert isinstance(result, AnalyticsInterpretation)
    signature = inspect.signature(command.interpret_analytics_snapshot)
    for forbidden in (
        "classification",
        "confidence",
        "strengths",
        "weaknesses",
        "summary",
    ):
        assert forbidden not in signature.parameters


@pytest.fixture()
def route_context():
    repository, control, mission, queue, publication, snapshot = _context()
    runtime = SimpleNamespace(mission_control=control)
    commands = MissionCommandService(runtime)
    app = create_app(
        dashboard_service=DashboardService(mission_control_service=control),
        mission_control_service=control,
        runtime_manager=runtime,
        mission_command_service=commands,
    )
    return TestClient(app), control, mission, queue, publication, snapshot


def _page_path(mission, snapshot):
    return (
        f"/missions/{mission.mission_id}/analytics/"
        f"{snapshot.analytics_snapshot_id}/interpretation"
    )


def _post_path(mission, snapshot):
    return (
        f"/missions/{mission.mission_id}/analytics/"
        f"{snapshot.analytics_snapshot_id}/interpret"
    )


def test_get_page_and_post_workflow_render_durable_interpretation(route_context):
    client, _, mission, _, _, snapshot = route_context
    page = client.get(_page_path(mission, snapshot))
    token = re.search(
        r'name="csrf_token" value="([^"]+)"',
        page.text,
    ).group(1)
    assert page.status_code == 200
    assert str(snapshot.analytics_snapshot_id) in page.text
    assert "recommendation" not in page.text.casefold()

    response = client.post(
        _post_path(mission, snapshot),
        data={"csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 303
    rendered = client.get(_page_path(mission, snapshot))
    assert RULESET_VERSION in rendered.text
    assert "Confidence" in rendered.text
    assert "Strengths" in rendered.text
    assert "Weaknesses" in rendered.text
    assert "Missing evidence" in rendered.text


@pytest.mark.parametrize(
    "body",
    [
        b"",
        b"csrf_token=" + b"x" * 32,
        b"csrf_token=" + b"x" * 32 + b"&csrf_token=" + b"y" * 32,
        b"csrf_token=" + b"x" * 32 + b"&classification=strong",
    ],
)
def test_post_rejects_csrf_repetition_and_unknown_fields(route_context, body):
    client, _, mission, _, _, snapshot = route_context
    client.get(_page_path(mission, snapshot))
    response = client.post(
        _post_path(mission, snapshot),
        content=body,
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code in {403, 422}


def test_post_body_size_and_local_boundary(route_context):
    client, _, mission, _, _, snapshot = route_context
    assert client.post(
        _post_path(mission, snapshot),
        content=b"csrf_token=" + b"x" * 13_000,
        headers={"content-type": "application/x-www-form-urlencoded"},
    ).status_code == 413
    remote = TestClient(client.app, client=("remote.example", 50_000))
    assert remote.post(
        _post_path(mission, snapshot),
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
    client, _, mission, _, _, snapshot = route_context
    page = client.get(_page_path(mission, snapshot))
    token = re.search(
        r'name="csrf_token" value="([^"]+)"',
        page.text,
    ).group(1)

    def fail(**_values):
        raise error

    monkeypatch.setattr(
        client.app.state.mission_command_service,
        "interpret_analytics_snapshot",
        fail,
    )
    response = client.post(
        _post_path(mission, snapshot),
        data={"csrf_token": token},
    )
    assert response.status_code == status
    if status == 503:
        assert "database details" not in response.text
        assert "consistency details" not in response.text


def test_get_missing_and_mismatch_paths_are_safe(route_context):
    client, control, mission, _, _, snapshot = route_context
    assert client.get(
        f"/missions/{uuid4()}/analytics/{snapshot.analytics_snapshot_id}/interpretation"
    ).status_code == 404
    assert client.get(
        f"/missions/{mission.mission_id}/analytics/{uuid4()}/interpretation"
    ).status_code == 404
    other = MissionRecord(
        title="Other",
        objective="Other",
        founder_owner="Founder",
    )
    control.repository.save_mission(other)
    assert client.get(
        f"/missions/{other.mission_id}/analytics/{snapshot.analytics_snapshot_id}/interpretation"
    ).status_code == 422


def test_dashboard_projection_empty_then_typed_interpretation(route_context):
    _, control, mission, _, publication, snapshot = route_context
    before = build_operations_projection(control).publishing_queue[0]
    assert isinstance(
        before.analytics.interpretation,
        DashboardAnalyticsInterpretation,
    )
    assert before.analytics.interpretation.interpretation_count == 0
    assert before.analytics.interpretation.interpretation_actionable is True

    created = control.interpret_analytics_snapshot(
        mission_id=mission.mission_id,
        analytics_snapshot_id=snapshot.analytics_snapshot_id,
        interpreted_by_actor="Founder",
    )
    after = build_operations_projection(control).publishing_queue[0].analytics
    assert isinstance(
        after.interpretation.latest_interpretation,
        AnalyticsInterpretation,
    )
    assert after.interpretation.latest_interpretation == created
    assert after.interpretation.interpretation_count == 1
    assert after.interpretation.source_analytics_snapshot_id == (
        snapshot.analytics_snapshot_id
    )
    assert after.interpretation.interpretation_actionable is False
    assert "already exists" in (
        after.interpretation.interpretation_blocking_reason
    )
