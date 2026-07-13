"""Deterministic in-memory runtime event bus."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from core import ValidationError, get_logger
from runtime_engine.models import (
    RuntimeEvent,
    RuntimeEventSeverity,
    RuntimeEventType,
)


class RuntimeEventBus:
    def __init__(self, maximum_events: int = 1000) -> None:
        if maximum_events <= 0:
            raise ValidationError("maximum_events must be greater than zero.")
        self._maximum_events = maximum_events
        self._events: list[RuntimeEvent] = []
        self.logger = get_logger("runtime_engine.event_bus")

    def publish(self, event: RuntimeEvent) -> RuntimeEvent:
        self._events.append(event)
        overflow = len(self._events) - self._maximum_events
        if overflow > 0:
            del self._events[:overflow]
        self.logger.info("Runtime event published: %s", event.event_type.value)
        return event

    def emit(
        self,
        event_type: RuntimeEventType,
        message: str,
        *,
        severity: RuntimeEventSeverity = RuntimeEventSeverity.INFO,
        **values: Any,
    ) -> RuntimeEvent:
        return self.publish(
            RuntimeEvent(
                event_type=event_type,
                message=message,
                severity=severity,
                **values,
            )
        )

    def list_events(self) -> tuple[RuntimeEvent, ...]:
        return tuple(self._events)

    def recent(self, limit: int) -> tuple[RuntimeEvent, ...]:
        self._validate_limit(limit)
        return tuple(self._events[-limit:])

    def filter_by_mission(self, mission_id: UUID) -> tuple[RuntimeEvent, ...]:
        return tuple(e for e in self._events if e.mission_id == mission_id)

    def filter_by_workflow(self, workflow_id: UUID) -> tuple[RuntimeEvent, ...]:
        return tuple(e for e in self._events if e.workflow_id == workflow_id)

    def filter_by_agent(self, agent_id: UUID) -> tuple[RuntimeEvent, ...]:
        return tuple(e for e in self._events if e.agent_id == agent_id)

    def filter_by_type(
        self, event_type: RuntimeEventType
    ) -> tuple[RuntimeEvent, ...]:
        return tuple(e for e in self._events if e.event_type == event_type)

    def count(self) -> int:
        return len(self._events)

    def clear(self) -> None:
        self._events.clear()
        self.logger.info("Runtime events cleared.")

    @staticmethod
    def _validate_limit(limit: int) -> None:
        if limit <= 0:
            raise ValidationError("Event limit must be greater than zero.")
