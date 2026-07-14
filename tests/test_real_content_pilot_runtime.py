"""Safe runtime event and partial-state projections."""

from company_missions.real_content_pilot import run_deterministic_real_content_pilot
from runtime_engine.models import RuntimeEventType


def test_runtime_events_are_ordered_and_state_is_summary_only() -> None:
    pilot, result = run_deterministic_real_content_pilot()
    events = pilot.event_bus.filter_by_mission(result.mission.mission_id)
    event_types = [event.event_type for event in events]

    assert event_types[0] == RuntimeEventType.REAL_MISSION_CREATED
    assert event_types[-1] == RuntimeEventType.FOUNDER_REVIEW_READY
    assert RuntimeEventType.SCRIPT_ARTIFACT_CREATED in event_types
    runtime = result.runtime_snapshot["real_content_pilot"]
    assert runtime["artifact_count"] >= 5
    assert "script" not in runtime
    assert "prompt" not in result.model_dump_json().lower()
