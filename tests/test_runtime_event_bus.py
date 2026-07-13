"""Tests for the deterministic runtime event bus."""

from uuid import uuid4

import pytest

from core import ValidationError
from runtime_engine.event_bus import RuntimeEventBus
from runtime_engine.models import RuntimeEvent, RuntimeEventType


def test_publish_order_recent_and_filters() -> None:
    bus = RuntimeEventBus()
    mission_id, workflow_id, agent_id = uuid4(), uuid4(), uuid4()
    first = bus.emit(
        RuntimeEventType.MISSION_REGISTERED,
        "Mission registered.",
        mission_id=mission_id,
    )
    second = bus.emit(
        RuntimeEventType.WORKFLOW_STARTED,
        "Workflow started.",
        workflow_id=workflow_id,
        agent_id=agent_id,
    )

    assert bus.list_events() == (first, second)
    assert bus.recent(1) == (second,)
    assert bus.filter_by_mission(mission_id) == (first,)
    assert bus.filter_by_workflow(workflow_id) == (second,)
    assert bus.filter_by_agent(agent_id) == (second,)
    assert bus.filter_by_type(RuntimeEventType.WORKFLOW_STARTED) == (second,)


def test_retention_clear_and_invalid_limits() -> None:
    bus = RuntimeEventBus(maximum_events=2)
    for index in range(3):
        bus.publish(
            RuntimeEvent(
                event_type=RuntimeEventType.WARNING,
                message=f"Warning {index}",
            )
        )
    assert bus.count() == 2
    assert bus.list_events()[0].message == "Warning 1"
    bus.clear()
    assert bus.list_events() == ()
    with pytest.raises(ValidationError):
        bus.recent(0)
    with pytest.raises(ValidationError):
        RuntimeEventBus(maximum_events=0)
