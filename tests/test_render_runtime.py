from pathlib import Path

from runtime_engine.event_bus import RuntimeEventBus
from runtime_engine.models import RuntimeEventType


def test_render_events_are_supported() -> None:
    bus = RuntimeEventBus()
    event = bus.emit(RuntimeEventType.RENDER_REQUESTED, "Render requested.")
    assert event.event_type == RuntimeEventType.RENDER_REQUESTED
