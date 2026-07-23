"""Phase 4 Milestone 5 founder-controlled closed learning loop tests."""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.dashboard.operations_v2 import build_operations_projection
from app.dashboard.service import DashboardService
from app.main import create_app
from app.runtime.mission_commands import MissionCommandService
from mission_control.models import (
    ConflictingDecisionError,
    MissionControlStatus,
    RecommendationDecision,
    RecommendationMissionLineage,
)
from mission_control.repository import (
    MissionControlRepository,
    SQLiteMissionControlRepository,
)
from test_phase4_milestone4_mission_recommendations import (
    _create_recommendation,
    _recommendation_context,
)


def _accepted_context():
    values = _recommendation_context()
    repository, control, mission, _, _, _, _, lesson = values
    recommendation = _create_recommendation(control, mission, lesson)
    accepted = control.review_mission_recommendation(
        mission_id=mission.mission_id,
        mission_recommendation_id=recommendation.mission_recommendation_id,
        decision=RecommendationDecision.ACCEPT,
        decided_by_actor="Founder",
        founder_note="Use for a future mission.",
    )
    return (*values, accepted)


def _create_successor(control, mission, recommendation):
    return control.create_mission_from_recommendation(
        source_mission_id=mission.mission_id,
        mission_recommendation_id=(
            recommendation.mission_recommendation_id
        ),
        created_by_actor="Founder",
    )


def test_accepted_recommendation_creates_ordinary_created_mission_and_lineage():
    repository, control, source, queue, publication, snapshot, interpretation, lesson, recommendation = (
        _accepted_context()
    )
    successor = _create_successor(control, source, recommendation)
    lineage = repository.find_recommendation_mission_lineage(
        recommendation.mission_recommendation_id
    )

    assert successor.status == MissionControlStatus.CREATED
    assert successor.mission_id != source.mission_id
    assert repository.list_tasks(successor.mission_id) == []
    assert lineage == RecommendationMissionLineage(
        successor_mission_id=successor.mission_id,
        source_recommendation_id=recommendation.mission_recommendation_id,
        source_lesson_id=lesson.mission_lesson_id,
        source_interpretation_id=(
            interpretation.analytics_interpretation_id
        ),
        source_snapshot_id=snapshot.analytics_snapshot_id,
        source_publication_id=publication.publication_id,
        source_queue_item_id=queue.queue_item_id,
        source_mission_id=source.mission_id,
        created_at=lineage.created_at,
        created_by_actor="Founder",
    )


@pytest.mark.parametrize(
    "decision",
    [None, RecommendationDecision.REJECT],
)
def test_pending_and_rejected_recommendations_cannot_create(decision):
    _, control, mission, _, _, _, _, lesson = _recommendation_context()
    recommendation = _create_recommendation(control, mission, lesson)
    if decision:
        recommendation = control.review_mission_recommendation(
            mission_id=mission.mission_id,
            mission_recommendation_id=(
                recommendation.mission_recommendation_id
            ),
            decision=decision,
            decided_by_actor="Founder",
        )
    with pytest.raises(ConflictingDecisionError):
        _create_successor(control, mission, recommendation)
    assert len(control.list_missions()) == 1


def test_repeated_and_concurrent_creation_return_single_winner():
    _, control, source, _, _, _, _, _, recommendation = _accepted_context()

    with ThreadPoolExecutor(max_workers=4) as pool:
        values = list(pool.map(
            lambda _: _create_successor(control, source, recommendation),
            range(4),
        ))
    again = _create_successor(control, source, recommendation)

    assert len({item.mission_id for item in (*values, again)}) == 1
    assert len(control.list_missions()) == 2
    events = [
        event for event in control.list_events()
        if event.event_type == "mission.created_from_recommendation"
    ]
    assert len(events) == 1


def test_creation_event_is_compact_and_complete():
    repository, control, source, queue, publication, snapshot, interpretation, lesson, recommendation = (
        _accepted_context()
    )
    successor = _create_successor(control, source, recommendation)
    event = next(
        item for item in repository.list_events()
        if item.event_type == "mission.created_from_recommendation"
    )
    assert event.mission_id == successor.mission_id
    assert set(event.payload) == {
        "new_mission_id",
        "recommendation_id",
        "lesson_id",
        "interpretation_id",
        "snapshot_id",
        "publication_id",
        "source_mission_id",
        "actor",
        "timestamp",
    }


def test_repository_contract_and_schema_v6_migration(tmp_path):
    for name in (
        "save_recommendation_mission_lineage",
        "find_recommendation_mission_lineage",
        "find_successor_mission_lineage",
    ):
        assert name in MissionControlRepository.__abstractmethods__

    path = tmp_path / "control.db"
    repository = SQLiteMissionControlRepository(path, allowed_root=tmp_path)
    assert repository.SCHEMA_VERSION == 6
    assert {
        "source_recommendation_id",
        "successor_mission_id",
        "source_mission_id",
        "data",
    } <= {
        row[1]
        for row in repository.connection.execute(
            "PRAGMA table_info(recommendation_mission_lineage)"
        )
    }
    repository.connection.execute(
        "DROP TABLE recommendation_mission_lineage"
    )
    repository.connection.execute("UPDATE schema_version SET version = 5")
    repository.connection.close()
    reopened = SQLiteMissionControlRepository(path, allowed_root=tmp_path)
    assert reopened.connection.execute(
        "SELECT version FROM schema_version"
    ).fetchone()[0] == 6


def test_command_delegates_to_mission_control():
    _, control, source, _, _, _, _, _, recommendation = _accepted_context()
    command = MissionCommandService(SimpleNamespace(mission_control=control))
    successor = command.create_mission_from_recommendation(
        source_mission_id=source.mission_id,
        mission_recommendation_id=(
            recommendation.mission_recommendation_id
        ),
        actor="Local Founder",
    )
    assert control.get_mission(successor.mission_id) == successor


@pytest.fixture()
def route_context():
    _, control, source, _, _, _, _, lesson, recommendation = (
        _accepted_context()
    )
    runtime = SimpleNamespace(mission_control=control)
    app = create_app(
        dashboard_service=DashboardService(mission_control_service=control),
        mission_control_service=control,
        runtime_manager=runtime,
        mission_command_service=MissionCommandService(runtime),
    )
    return TestClient(app), control, source, lesson, recommendation


def _recommendation_path(source, lesson):
    return (
        f"/missions/{source.mission_id}/lessons/"
        f"{lesson.mission_lesson_id}/recommendation"
    )


def test_dashboard_route_requires_explicit_post_and_links_both_directions(
    route_context,
):
    client, control, source, lesson, recommendation = route_context
    path = _recommendation_path(source, lesson)
    page = client.get(path)
    assert "Create Mission From Recommendation" in page.text
    assert len(control.list_missions()) == 1
    token = re.search(
        r'name="csrf_token" value="([^"]+)"', page.text
    ).group(1)
    post = (
        f"/missions/{source.mission_id}/recommendations/"
        f"{recommendation.mission_recommendation_id}/create-mission"
    )
    assert client.get(post).status_code == 405
    response = client.post(
        post,
        data={"csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 303
    successor = control.list_missions()[-1]
    review = client.get(f"/missions/{successor.mission_id}/review")
    assert "View source recommendation" in review.text
    refreshed = client.get(path)
    assert "View successor mission" in refreshed.text


def test_route_enforces_csrf_unknown_fields_and_local_boundary(route_context):
    client, _, source, lesson, recommendation = route_context
    page = client.get(_recommendation_path(source, lesson))
    post = (
        f"/missions/{source.mission_id}/recommendations/"
        f"{recommendation.mission_recommendation_id}/create-mission"
    )
    assert client.post(
        post, data={"csrf_token": "x" * 32}
    ).status_code == 403
    token = client.cookies["auraai_csrf"]
    assert client.post(
        post,
        data={"csrf_token": token, "title": "Injected"},
    ).status_code == 422
    remote = TestClient(client.app, client=("remote.example", 50000))
    assert remote.post(
        post, data={"csrf_token": token}
    ).status_code == 403


def test_dashboard_projection_shows_successor_eligibility_and_identity():
    _, control, source, _, _, _, _, _, recommendation = _accepted_context()
    before = (
        build_operations_projection(control).publishing_queue[0]
        .analytics.interpretation.lesson.recommendation
    )
    assert before.successor_creation_actionable is True
    assert before.successor_exists is False
    successor = _create_successor(control, source, recommendation)
    after = (
        build_operations_projection(control).publishing_queue[0]
        .analytics.interpretation.lesson.recommendation
    )
    assert after.successor_exists is True
    assert after.successor_mission_id == successor.mission_id
    assert after.successor_creation_actionable is False


def test_no_automatic_creation_after_acceptance():
    _, control, source, _, _, _, _, _, recommendation = _accepted_context()
    assert recommendation.status.value == "accepted"
    assert len(control.list_missions()) == 1
    assert control.repository.find_recommendation_mission_lineage(
        recommendation.mission_recommendation_id
    ) is None
