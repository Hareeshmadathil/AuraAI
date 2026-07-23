"""Phase 4 Milestone 1: Analytics Import Foundation Tests."""

from __future__ import annotations
import pathlib
import inspect

import decimal
from datetime import UTC, datetime, timedelta, timezone
import sqlite3
import threading
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.dashboard.operations_v2 import build_operations_projection
from app.dashboard.service import DashboardService
from app.main import create_app
from core import utc_now
from mission_control.models import (
    AnalyticsMetrics,
    AnalyticsSnapshot,
    DuplicateRecordError,
    RepositoryConsistencyError,
    RepositoryIntegrityError,
    ItemNotFoundError,
    ConflictingDecisionError,
    MalformedCommandError,
    MismatchError,
    MissionRecord,
    StaleContentError,
    PublishingQueueStatus,
    PublicationRecord,
    PublishingQueueItem,
)
from mission_control.repository import (
    InMemoryMissionControlRepository,
    MissionControlRepository,
    SQLiteMissionControlRepository,
)
from mission_control.service import MissionControlService

def test_decimal_normalization_hashing(tmp_path):
    # Decimal 10.50 and 10.5 produce the same payload hash
    # Decimal 10.00 and 10 produce the same payload hash
    metrics1 = AnalyticsMetrics(revenue_amount=Decimal("10.50"), revenue_currency="USD", views=100)
    metrics2 = AnalyticsMetrics(revenue_amount=Decimal("10.5"), revenue_currency="USD", views=100)

    # We test via the service method _generate_payload_hash
    service = MissionControlService(SQLiteMissionControlRepository(tmp_path / "mc.db", allowed_root=tmp_path))
    hash1 = service._generate_payload_hash(metrics1)
    hash2 = service._generate_payload_hash(metrics2)
    assert hash1 == hash2

    metrics3 = AnalyticsMetrics(revenue_amount=Decimal("10.00"), revenue_currency="USD", views=100)
    metrics4 = AnalyticsMetrics(revenue_amount=Decimal("10"), revenue_currency="USD", views=100)
    assert service._generate_payload_hash(metrics3) == service._generate_payload_hash(metrics4)

def test_non_finite_decimal_rejected():
    with pytest.raises(ValueError, match="finite"):
        AnalyticsMetrics(revenue_amount=Decimal("NaN"), revenue_currency="USD", views=100)
    with pytest.raises(ValueError, match="finite"):
        AnalyticsMetrics(revenue_amount=Decimal("Infinity"), revenue_currency="USD", views=100)

def test_import_note_without_metric_rejected():
    with pytest.raises(ValueError, match="measurable numeric metric"):
        AnalyticsMetrics(import_note="Just a note")

def test_missing_currency_when_revenue_present():
    with pytest.raises(ValueError, match="revenue_currency cannot be provided without revenue_amount"):
        AnalyticsMetrics(revenue_currency="USD", views=10)

def test_currency_is_uppercased():
    metrics = AnalyticsMetrics(revenue_amount=Decimal("10"), revenue_currency="usd", views=10)
    assert metrics.revenue_currency == "USD"

def test_sqlite_schema_and_integrity_translation(tmp_path):
    repo = SQLiteMissionControlRepository(tmp_path / "mc.db", allowed_root=tmp_path)

    mission_id = uuid4()
    queue_item_id = uuid4()
    publication_id = uuid4()

    # Needs valid mission etc due to FKs
    repo.connection.execute("PRAGMA foreign_keys = OFF;")

    snapshot = AnalyticsSnapshot(
        mission_id=mission_id,
        publication_id=publication_id,
        queue_item_id=queue_item_id,
        destination="test",
        observed_at=utc_now(),
        imported_at=utc_now(),
        imported_by_actor="test",
        payload_hash="a" * 64,
        metrics=AnalyticsMetrics(views=1)
    )

    repo.save_analytics_snapshot(snapshot)

    # Duplicate insert raises DuplicateRecordError
    snapshot2 = AnalyticsSnapshot(
        analytics_snapshot_id=uuid4(),
        mission_id=mission_id,
        publication_id=publication_id,
        queue_item_id=queue_item_id,
        destination="test",
        observed_at=snapshot.observed_at,
        imported_at=utc_now(),
        imported_by_actor="test",
        payload_hash="b" * 64,
        metrics=AnalyticsMetrics(views=2)
    )
    with pytest.raises(DuplicateRecordError):
        repo.save_analytics_snapshot(snapshot2)

    # Unrelated integrity error (e.g. foreign key violation)
    repo.connection.execute("PRAGMA foreign_keys = ON;")
    snapshot3 = AnalyticsSnapshot(
        analytics_snapshot_id=uuid4(),
        mission_id=uuid4(), # This doesn't exist in missions table!
        publication_id=publication_id,
        queue_item_id=queue_item_id,
        destination="test",
        observed_at=utc_now(),
        imported_at=utc_now(),
        imported_by_actor="test",
        payload_hash="c" * 64,
        metrics=AnalyticsMetrics(views=3)
    )
    with pytest.raises(RepositoryIntegrityError):
        repo.save_analytics_snapshot(snapshot3)

def test_sequential_retry(tmp_path):
    repo = SQLiteMissionControlRepository(tmp_path / "mc.db", allowed_root=tmp_path)
    repo.connection.execute("PRAGMA foreign_keys = OFF;")
    service = MissionControlService(repo)

    mission_id = uuid4()
    queue_item_id = uuid4()
    publication_id = uuid4()
    observed_at = utc_now()

    repo.connection.execute("INSERT INTO missions(id, data) VALUES (?, ?)", (str(mission_id), "{}"))
    q = PublishingQueueItem(mission_id=mission_id, manifest_id=uuid4(), source_package_id=uuid4(), target_platforms=["x"], queue_item_id=queue_item_id, destination="x", manifest_hash="0"*64, status=PublishingQueueStatus.PUBLISHED_CONFIRMED)
    repo.save_publishing_queue_item(q)

    p = PublicationRecord(mission_id=mission_id, queue_item_id=queue_item_id, publication_id=publication_id, destination="x", content_hash="0"*64, published_by_actor="a")
    repo.save_publication_record(p)

    metrics = AnalyticsMetrics(views=10)

    s1 = service.import_analytics_snapshot(
        mission_id=mission_id, publication_id=publication_id, observed_at=observed_at, imported_by_actor="a", metrics=metrics
    )

    # Idempotent retry
    s2 = service.import_analytics_snapshot(
        mission_id=mission_id, publication_id=publication_id, observed_at=observed_at, imported_by_actor="a", metrics=metrics
    )

    assert s1.analytics_snapshot_id == s2.analytics_snapshot_id
    events = [e for e in repo.list_events() if e.event_type == "analytics.snapshot_imported"]
    assert len(events) == 1

def test_sequential_conflict(tmp_path):
    repo = SQLiteMissionControlRepository(tmp_path / "mc.db", allowed_root=tmp_path)
    repo.connection.execute("PRAGMA foreign_keys = OFF;")
    service = MissionControlService(repo)

    mission_id = uuid4()
    queue_item_id = uuid4()
    publication_id = uuid4()
    observed_at = utc_now()

    repo.connection.execute("INSERT INTO missions(id, data) VALUES (?, ?)", (str(mission_id), "{}"))
    q = PublishingQueueItem(mission_id=mission_id, manifest_id=uuid4(), source_package_id=uuid4(), target_platforms=["x"], queue_item_id=queue_item_id, destination="x", manifest_hash="0"*64, status=PublishingQueueStatus.PUBLISHED_CONFIRMED)
    repo.save_publishing_queue_item(q)

    p = PublicationRecord(mission_id=mission_id, queue_item_id=queue_item_id, publication_id=publication_id, destination="x", content_hash="0"*64, published_by_actor="a")
    repo.save_publication_record(p)

    service.import_analytics_snapshot(
        mission_id=mission_id, publication_id=publication_id, observed_at=observed_at, imported_by_actor="a", metrics=AnalyticsMetrics(views=10)
    )

    # Different payload
    with pytest.raises(ConflictingDecisionError):
        service.import_analytics_snapshot(
            mission_id=mission_id, publication_id=publication_id, observed_at=observed_at, imported_by_actor="a", metrics=AnalyticsMetrics(views=20)
        )


def _snapshot(
    *,
    publication_id=None,
    observed_at=None,
    imported_at=None,
    snapshot_id=None,
) -> AnalyticsSnapshot:
    return AnalyticsSnapshot(
        analytics_snapshot_id=snapshot_id or uuid4(),
        mission_id=uuid4(),
        publication_id=publication_id or uuid4(),
        queue_item_id=uuid4(),
        destination="youtube",
        observed_at=observed_at or utc_now(),
        imported_at=imported_at or utc_now(),
        imported_by_actor="founder",
        payload_hash="a" * 64,
        metrics=AnalyticsMetrics(views=1),
    )


def _in_memory_publication_context():
    repository = InMemoryMissionControlRepository()
    mission_id = uuid4()
    queue_item = PublishingQueueItem(
        mission_id=mission_id,
        manifest_id=uuid4(),
        source_package_id=uuid4(),
        target_platforms=["youtube"],
        destination="youtube",
        manifest_hash="a" * 64,
        status=PublishingQueueStatus.PUBLISHED_CONFIRMED,
    )
    publication = PublicationRecord(
        mission_id=mission_id,
        queue_item_id=queue_item.queue_item_id,
        destination=queue_item.destination,
        content_hash=queue_item.manifest_hash,
        published_by_actor="founder",
    )
    repository.save_publishing_queue_item(queue_item)
    repository.save_publication_record(publication)
    return repository, mission_id, queue_item, publication


def test_analytics_methods_belong_to_repository_contract():
    for method_name in (
        "save_analytics_snapshot",
        "find_snapshot_by_id",
        "find_observation_snapshot",
        "list_analytics_snapshots",
    ):
        assert method_name in MissionControlRepository.__abstractmethods__


def test_in_memory_analytics_save_and_lookup():
    repository = InMemoryMissionControlRepository()
    snapshot = _snapshot()

    repository.save_analytics_snapshot(snapshot)

    assert (
        repository.find_snapshot_by_id(snapshot.analytics_snapshot_id)
        == snapshot
    )
    assert (
        repository.find_observation_snapshot(
            snapshot.publication_id,
            snapshot.observed_at,
        )
        == snapshot
    )


def test_in_memory_analytics_history_ordering():
    repository = InMemoryMissionControlRepository()
    publication_id = uuid4()
    older = utc_now() - timedelta(hours=1)
    observed_at = utc_now()
    first = _snapshot(
        publication_id=publication_id,
        observed_at=older,
        snapshot_id=UUID(int=1),
    )
    second = _snapshot(
        publication_id=publication_id,
        observed_at=observed_at - timedelta(seconds=1),
        imported_at=observed_at - timedelta(seconds=1),
        snapshot_id=UUID(int=2),
    )
    third = _snapshot(
        publication_id=publication_id,
        observed_at=observed_at,
        imported_at=observed_at,
        snapshot_id=UUID(int=3),
    )
    for snapshot in (first, second, third):
        repository.save_analytics_snapshot(snapshot)

    assert repository.list_analytics_snapshots(publication_id) == [
        third,
        second,
        first,
    ]


def test_in_memory_duplicate_observation_rejected():
    repository = InMemoryMissionControlRepository()
    snapshot = _snapshot()
    duplicate = snapshot.model_copy(
        update={"analytics_snapshot_id": uuid4(), "payload_hash": "b" * 64}
    )
    repository.save_analytics_snapshot(snapshot)

    with pytest.raises(DuplicateRecordError):
        repository.save_analytics_snapshot(duplicate)


def test_in_memory_publication_lookup_uses_memory():
    repository, _, _, publication = _in_memory_publication_context()

    assert (
        repository.get_publication_record_by_id(publication.publication_id)
        == publication
    )


def test_service_error_branches_resolve_domain_names():
    repository, mission_id, _, publication = _in_memory_publication_context()
    service = MissionControlService(repository)

    with pytest.raises(StaleContentError):
        service.import_analytics_snapshot(
            mission_id=mission_id,
            publication_id=publication.publication_id,
            observed_at=utc_now() + timedelta(minutes=6),
            imported_by_actor="founder",
            metrics=AnalyticsMetrics(views=1),
        )
    with pytest.raises(ItemNotFoundError):
        service.import_analytics_snapshot(
            mission_id=mission_id,
            publication_id=uuid4(),
            observed_at=utc_now(),
            imported_by_actor="founder",
            metrics=AnalyticsMetrics(views=1),
        )


def test_service_rejects_mismatched_publication_mission():
    repository, mission_id, _, publication = _in_memory_publication_context()

    with pytest.raises(MismatchError, match="Publication record mission"):
        MissionControlService(repository).import_analytics_snapshot(
            mission_id=uuid4(),
            publication_id=publication.publication_id,
            observed_at=utc_now(),
            imported_by_actor="founder",
            metrics=AnalyticsMetrics(views=1),
        )


def test_service_rejects_mismatched_queue_mission():
    repository, mission_id, queue_item, publication = (
        _in_memory_publication_context()
    )
    repository.update_publishing_queue_item(
        queue_item.model_copy(update={"mission_id": uuid4()})
    )

    with pytest.raises(MismatchError, match="queue item mission"):
        MissionControlService(repository).import_analytics_snapshot(
            mission_id=mission_id,
            publication_id=publication.publication_id,
            observed_at=utc_now(),
            imported_by_actor="founder",
            metrics=AnalyticsMetrics(views=1),
        )


@pytest.mark.parametrize(
    ("publication_update", "message"),
    [
        ({"destination": "tiktok"}, "destination"),
        ({"content_hash": "b" * 64}, "content hash"),
    ],
)
def test_service_rejects_publication_identity_mismatch(
    publication_update,
    message,
):
    repository, mission_id, _, publication = _in_memory_publication_context()
    repository.publication_records[publication.queue_item_id] = (
        publication.model_copy(update=publication_update)
    )

    with pytest.raises(MismatchError, match=message):
        MissionControlService(repository).import_analytics_snapshot(
            mission_id=mission_id,
            publication_id=publication.publication_id,
            observed_at=utc_now(),
            imported_by_actor="founder",
            metrics=AnalyticsMetrics(views=1),
        )


def _configure_collision(repository, service, winner, monkeypatch):
    lookups = iter((None, winner))
    monkeypatch.setattr(
        repository,
        "find_observation_snapshot",
        lambda *_: next(lookups),
    )

    def raise_duplicate(_snapshot):
        raise DuplicateRecordError("concurrent collision")

    monkeypatch.setattr(
        repository,
        "save_analytics_snapshot",
        raise_duplicate,
    )
    appended_events = []
    monkeypatch.setattr(
        repository,
        "append_event",
        appended_events.append,
    )
    return appended_events


def test_identical_collision_recovery_returns_winner(monkeypatch):
    repository, mission_id, _, publication = _in_memory_publication_context()
    service = MissionControlService(repository)
    metrics = AnalyticsMetrics(views=12)
    observed_at = utc_now()
    winner = _snapshot(
        publication_id=publication.publication_id,
        observed_at=observed_at,
    ).model_copy(
        update={
            "mission_id": mission_id,
            "queue_item_id": publication.queue_item_id,
            "payload_hash": service._generate_payload_hash(metrics),
        }
    )
    appended_events = _configure_collision(
        repository,
        service,
        winner,
        monkeypatch,
    )

    result = service.import_analytics_snapshot(
        mission_id=mission_id,
        publication_id=publication.publication_id,
        observed_at=observed_at,
        imported_by_actor="founder",
        metrics=metrics,
    )

    assert result == winner
    assert appended_events == []


def test_conflicting_collision_recovery_raises(monkeypatch):
    repository, mission_id, _, publication = _in_memory_publication_context()
    service = MissionControlService(repository)
    observed_at = utc_now()
    winner = _snapshot(
        publication_id=publication.publication_id,
        observed_at=observed_at,
    ).model_copy(
        update={
            "mission_id": mission_id,
            "queue_item_id": publication.queue_item_id,
            "payload_hash": "f" * 64,
        }
    )
    appended_events = _configure_collision(
        repository,
        service,
        winner,
        monkeypatch,
    )

    with pytest.raises(ConflictingDecisionError):
        service.import_analytics_snapshot(
            mission_id=mission_id,
            publication_id=publication.publication_id,
            observed_at=observed_at,
            imported_by_actor="founder",
            metrics=AnalyticsMetrics(views=12),
        )
    assert appended_events == []


def test_collision_without_winner_raises_consistency_error(monkeypatch):
    repository, mission_id, _, publication = _in_memory_publication_context()
    service = MissionControlService(repository)
    monkeypatch.setattr(
        repository,
        "find_observation_snapshot",
        lambda *_: None,
    )

    def raise_duplicate(_snapshot):
        raise DuplicateRecordError("concurrent collision")

    monkeypatch.setattr(
        repository,
        "save_analytics_snapshot",
        raise_duplicate,
    )

    with pytest.raises(RepositoryConsistencyError):
        service.import_analytics_snapshot(
            mission_id=mission_id,
            publication_id=publication.publication_id,
            observed_at=utc_now(),
            imported_by_actor="founder",
            metrics=AnalyticsMetrics(views=12),
        )


def test_mission_control_service_has_no_sqlite_dependency():
    source = inspect.getsource(
        __import__(
            "mission_control.service",
            fromlist=["MissionControlService"],
        )
    )
    assert "sqlite3" not in source


def test_revenue_requires_currency():
    with pytest.raises(ValueError, match="requires revenue_currency"):
        AnalyticsMetrics(revenue_amount=Decimal("1.00"))


@pytest.mark.parametrize("currency", ["12A", "US", "USDX"])
def test_currency_requires_three_ascii_letters(currency):
    with pytest.raises(ValueError):
        AnalyticsMetrics(
            views=1,
            revenue_amount=Decimal("1.00"),
            revenue_currency=currency,
        )


def test_extra_metric_fields_are_rejected():
    with pytest.raises(ValueError):
        AnalyticsMetrics(views=1, unknown_metric=2)


@pytest.mark.parametrize(
    "field_name",
    ["observed_at", "imported_at"],
)
def test_snapshot_rejects_naive_timestamps(field_name):
    values = {
        "observed_at": utc_now(),
        "imported_at": utc_now(),
    }
    values[field_name] = datetime(2026, 1, 1, 12, 0)
    with pytest.raises(ValueError, match="timezone-aware UTC"):
        _snapshot(**values)


@pytest.mark.parametrize(
    "field_name",
    ["observed_at", "imported_at"],
)
def test_snapshot_rejects_non_utc_timestamps(field_name):
    values = {
        "observed_at": utc_now(),
        "imported_at": utc_now(),
    }
    values[field_name] = datetime(
        2026,
        1,
        1,
        12,
        0,
        tzinfo=timezone(timedelta(hours=1)),
    )
    with pytest.raises(ValueError, match="non-zero offset"):
        _snapshot(**values)


@pytest.mark.parametrize(
    ("minutes", "accepted"),
    [(5, True), (5.01, False)],
)
def test_service_enforces_future_clock_skew(monkeypatch, minutes, accepted):
    repository, mission_id, _, publication = _in_memory_publication_context()
    service = MissionControlService(repository)
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    monkeypatch.setattr("mission_control.service.utc_now", lambda: now)
    arguments = {
        "mission_id": mission_id,
        "publication_id": publication.publication_id,
        "observed_at": now + timedelta(minutes=minutes),
        "imported_by_actor": "founder",
        "metrics": AnalyticsMetrics(views=0),
    }
    if accepted:
        assert service.import_analytics_snapshot(**arguments).observed_at == (
            now + timedelta(minutes=minutes)
        )
    else:
        with pytest.raises(StaleContentError):
            service.import_analytics_snapshot(**arguments)


class _AnalyticsCommands:
    def __init__(self, control):
        self.runtime_manager = None
        self.control = control
        self.error = None
        self.received_metrics = None

    def import_analytics_snapshot(self, **values):
        if self.error is not None:
            raise self.error
        self.received_metrics = values["metrics"]
        return self.control.import_analytics_snapshot(
            mission_id=values["mission_id"],
            publication_id=values["publication_id"],
            observed_at=values["observed_at"],
            imported_by_actor=values["actor"],
            metrics=values["metrics"],
        )


@pytest.fixture()
def analytics_route_context():
    repository = InMemoryMissionControlRepository()
    control = MissionControlService(repository)
    mission = MissionRecord(
        title="Analytics mission",
        objective="Import source-reported analytics.",
        founder_owner="Founder",
        publishing_generation=1,
    )
    repository.save_mission(mission)
    queue_item = PublishingQueueItem(
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
        queue_item_id=queue_item.queue_item_id,
        destination=queue_item.destination,
        content_hash=queue_item.manifest_hash,
        external_url="https://example.test/video",
        published_by_actor="Founder",
    )
    repository.save_publishing_queue_item(queue_item)
    repository.save_publication_record(publication)
    commands = _AnalyticsCommands(control)
    dashboard = DashboardService(mission_control_service=control)
    application = create_app(
        dashboard_service=dashboard,
        mission_control_service=control,
        mission_command_service=commands,
    )
    return (
        TestClient(application),
        control,
        commands,
        mission,
        queue_item,
        publication,
    )


def _analytics_path(mission, publication):
    return (
        f"/missions/{mission.mission_id}/publications/"
        f"{publication.publication_id}/analytics/import"
    )


def _analytics_form(client, mission, publication):
    page = client.get(_analytics_path(mission, publication))
    assert page.status_code == 200
    token = client.cookies["auraai_csrf"]
    return {
        "csrf_token": token,
        "observed_at": "2026-01-01T12:00:00Z",
        "views": "0",
        "impressions": "",
        "likes": "",
        "comments": "",
        "shares": "",
        "saves": "",
        "clicks": "",
        "watch_time_seconds": "",
        "followers_gained": "",
        "revenue_amount": "",
        "revenue_currency": "",
        "import_note": "",
    }


def test_analytics_get_renders_standard_context_and_csrf(
    analytics_route_context,
):
    client, _, _, mission, _, publication = analytics_route_context
    response = client.get(_analytics_path(mission, publication))

    assert response.status_code == 200
    assert 'name="csrf_token"' in response.text
    assert "Analytics mission" in response.text
    assert publication.content_hash in response.text
    assert "No analytics snapshots" in response.text
    assert "Local interface only" in response.text
    assert client.cookies["auraai_csrf"]


def test_valid_analytics_post_accepts_zero_and_omits_empty_fields(
    analytics_route_context,
):
    client, _, commands, mission, _, publication = analytics_route_context
    form = _analytics_form(client, mission, publication)

    response = client.post(
        _analytics_path(mission, publication),
        data=form,
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert commands.received_metrics.views == 0
    assert commands.received_metrics.impressions is None
    assert "csrf_token" not in commands.received_metrics.model_fields_set


@pytest.mark.parametrize("csrf_value", [None, "x" * 32])
def test_analytics_post_rejects_missing_or_invalid_csrf(
    analytics_route_context,
    csrf_value,
):
    client, _, _, mission, _, publication = analytics_route_context
    form = _analytics_form(client, mission, publication)
    if csrf_value is None:
        form.pop("csrf_token")
    else:
        form["csrf_token"] = csrf_value

    response = client.post(_analytics_path(mission, publication), data=form)

    assert response.status_code in {403, 422}


@pytest.mark.parametrize(
    "timestamp",
    [
        "not-a-timestamp",
        "2026-01-01T12:00:00",
        "2026-01-01T12:00:00+01:00",
    ],
)
def test_analytics_post_rejects_invalid_or_non_utc_timestamp(
    analytics_route_context,
    timestamp,
):
    client, _, _, mission, _, publication = analytics_route_context
    form = _analytics_form(client, mission, publication)
    form["observed_at"] = timestamp

    response = client.post(_analytics_path(mission, publication), data=form)

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (ItemNotFoundError("missing"), 404),
        (ConflictingDecisionError("conflict"), 409),
        (StaleContentError("stale"), 409),
        (MismatchError("mismatch"), 422),
        (MalformedCommandError("malformed"), 422),
        (RepositoryIntegrityError("database details"), 503),
        (RepositoryConsistencyError("consistency details"), 503),
    ],
)
def test_analytics_post_maps_domain_errors_safely(
    analytics_route_context,
    error,
    status_code,
):
    client, _, commands, mission, _, publication = analytics_route_context
    form = _analytics_form(client, mission, publication)
    commands.error = error

    response = client.post(_analytics_path(mission, publication), data=form)

    assert response.status_code == status_code
    if status_code == 503:
        assert "database details" not in response.text
        assert "consistency details" not in response.text


def test_analytics_get_not_found_and_mismatch_are_not_500(
    analytics_route_context,
):
    client, control, _, mission, _, publication = analytics_route_context
    missing_mission = client.get(_analytics_path(
        mission.model_copy(update={"mission_id": uuid4()}),
        publication,
    ))
    missing_publication = client.get(_analytics_path(
        mission,
        publication.model_copy(update={"publication_id": uuid4()}),
    ))
    other_mission = MissionRecord(
        title="Other",
        objective="Other mission.",
        founder_owner="Founder",
    )
    control.repository.save_mission(other_mission)
    mismatch = client.get(_analytics_path(other_mission, publication))

    assert missing_mission.status_code == 404
    assert missing_publication.status_code == 404
    assert mismatch.status_code == 422


def test_dashboard_analytics_projection_orders_and_counts_snapshots(
    analytics_route_context,
):
    _, control, _, mission, _, publication = analytics_route_context
    older = _snapshot(
        publication_id=publication.publication_id,
        observed_at=datetime(2026, 1, 1, 11, 0, tzinfo=UTC),
        imported_at=datetime(2026, 1, 1, 11, 1, tzinfo=UTC),
    ).model_copy(
        update={
            "mission_id": mission.mission_id,
            "queue_item_id": publication.queue_item_id,
        }
    )
    latest = older.model_copy(
        update={
            "analytics_snapshot_id": uuid4(),
            "observed_at": datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
            "imported_at": datetime(2026, 1, 1, 12, 1, tzinfo=UTC),
        }
    )
    control.repository.save_analytics_snapshot(older)
    control.repository.save_analytics_snapshot(latest)

    projection = build_operations_projection(control)
    analytics = projection.publishing_queue[0].analytics

    assert isinstance(analytics.latest_snapshot, AnalyticsSnapshot)
    assert analytics.latest_snapshot == latest
    assert analytics.historical_snapshots == [older]
    assert analytics.snapshot_count == 2
    assert analytics.latest_observed_at == latest.observed_at.isoformat()
    assert analytics.latest_imported_at == latest.imported_at.isoformat()
    assert analytics.has_analytics is True
    assert analytics.analytics_actionable is True
    assert analytics.analytics_blocking_reason is None


def test_dashboard_empty_analytics_projection_is_explicit(
    analytics_route_context,
):
    _, control, _, _, _, _ = analytics_route_context

    analytics = build_operations_projection(
        control
    ).publishing_queue[0].analytics

    assert analytics.latest_snapshot is None
    assert analytics.historical_snapshots == []
    assert analytics.snapshot_count == 0
    assert analytics.latest_observed_at is None
    assert analytics.latest_imported_at is None
    assert analytics.has_analytics is False
    assert analytics.analytics_actionable is True
    assert analytics.analytics_blocking_reason is None


def test_analytics_get_renders_current_history(analytics_route_context):
    client, control, _, mission, _, publication = analytics_route_context
    snapshot = _snapshot(
        publication_id=publication.publication_id,
        observed_at=datetime(2026, 1, 1, 11, 0, tzinfo=UTC),
        imported_at=datetime(2026, 1, 1, 11, 1, tzinfo=UTC),
    ).model_copy(
        update={
            "mission_id": mission.mission_id,
            "queue_item_id": publication.queue_item_id,
        }
    )
    control.repository.save_analytics_snapshot(snapshot)

    response = client.get(_analytics_path(mission, publication))

    assert response.status_code == 200
    assert snapshot.observed_at.isoformat() in response.text
    assert snapshot.payload_hash in response.text
