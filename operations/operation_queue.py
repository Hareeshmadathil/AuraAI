"""
Mission operations queue for AuraAI Creator OS.

The COO uses this queue to organize approved company missions according
to priority and arrival order. The queue is intentionally independent
from databases and external task brokers so it can later be replaced
without changing the COO's public interface.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from uuid import UUID

from core import (
    MissionRecord,
    StorageError,
    TaskPriority,
    ValidationError,
    get_logger,
    utc_now,
)


_PRIORITY_RANK: dict[TaskPriority, int] = {
    TaskPriority.LOW: 1,
    TaskPriority.NORMAL: 2,
    TaskPriority.HIGH: 3,
    TaskPriority.CRITICAL: 4,
}


@dataclass(slots=True)
class _QueuedMission:
    """
    Internal queue entry.

    The sequence number guarantees stable first-in, first-out ordering
    when multiple missions have the same priority.
    """

    mission: MissionRecord
    queued_at: datetime
    sequence: int


class OperationQueue:
    """
    Thread-safe priority queue of approved AuraAI missions.

    Higher-priority missions are returned first. Missions with equal
    priority remain in the order in which they were added.
    """

    def __init__(self) -> None:
        self._entries: dict[UUID, _QueuedMission] = {}
        self._sequence = 0
        self._lock = RLock()
        self.logger = get_logger("operations.operation_queue")

    def enqueue(self, mission: MissionRecord) -> None:
        """
        Add an approved, non-terminal mission to the queue.

        Raises:
            ValidationError:
                If the mission is not eligible for operational work.
            StorageError:
                If the mission is already queued.
        """

        with self._lock:
            if mission.is_terminal:
                raise ValidationError(
                    "Terminal missions cannot enter the operations queue.",
                    details={
                        "mission_id": str(mission.mission_id),
                        "status": mission.status.value,
                    },
                )

            if not mission.is_approved:
                raise ValidationError(
                    "A mission must be approved before entering "
                    "the operations queue.",
                    details={
                        "mission_id": str(mission.mission_id),
                        "approval_status": (
                            mission.approval_status.value
                        ),
                    },
                )

            if mission.mission_id in self._entries:
                raise StorageError(
                    "Mission is already present in the operations queue.",
                    details={
                        "mission_id": str(mission.mission_id),
                    },
                )

            self._sequence += 1

            self._entries[mission.mission_id] = _QueuedMission(
                mission=mission,
                queued_at=utc_now(),
                sequence=self._sequence,
            )

            self.logger.info(
                "Mission queued: %s | mission_id=%s | priority=%s",
                mission.title,
                mission.mission_id,
                mission.priority.value,
            )

    def dequeue(self) -> MissionRecord:
        """
        Remove and return the next operational mission.

        Raises:
            StorageError:
                If the queue is empty.
        """

        with self._lock:
            entry = self._get_next_entry()
            del self._entries[entry.mission.mission_id]

            self.logger.info(
                "Mission dequeued: %s | mission_id=%s",
                entry.mission.title,
                entry.mission.mission_id,
            )

            return entry.mission

    def peek(self) -> MissionRecord:
        """
        Return the next mission without removing it.

        Raises:
            StorageError:
                If the queue is empty.
        """

        with self._lock:
            return self._get_next_entry().mission

    def remove(self, mission_id: UUID) -> MissionRecord:
        """
        Remove one queued mission by identifier.

        Raises:
            StorageError:
                If the mission is not in the queue.
        """

        with self._lock:
            try:
                entry = self._entries.pop(mission_id)
            except KeyError as error:
                raise StorageError(
                    "Mission was not found in the operations queue.",
                    details={
                        "mission_id": str(mission_id),
                    },
                ) from error

            self.logger.info(
                "Mission removed from queue: %s | mission_id=%s",
                entry.mission.title,
                mission_id,
            )

            return entry.mission

    def list_pending(self) -> list[MissionRecord]:
        """
        Return queued missions in operational execution order.
        """

        with self._lock:
            return [
                entry.mission
                for entry in sorted(
                    self._entries.values(),
                    key=self._sort_key,
                )
            ]

    def contains(self, mission_id: UUID) -> bool:
        """Return whether a mission is currently queued."""

        with self._lock:
            return mission_id in self._entries

    def count(self) -> int:
        """Return the number of queued missions."""

        with self._lock:
            return len(self._entries)

    def clear(self) -> None:
        """Remove every queued mission."""

        with self._lock:
            self._entries.clear()
            self.logger.info("Operations queue cleared.")

    def _get_next_entry(self) -> _QueuedMission:
        """Return the highest-priority internal queue entry."""

        if not self._entries:
            raise StorageError(
                "The operations queue is empty."
            )

        return min(
            self._entries.values(),
            key=self._sort_key,
        )

    @staticmethod
    def _sort_key(
        entry: _QueuedMission,
    ) -> tuple[int, datetime, int]:
        """
        Build a stable priority ordering key.

        The priority value is negated so critical missions sort before
        high, normal, and low-priority missions.
        """

        return (
            -_PRIORITY_RANK[entry.mission.priority],
            entry.queued_at,
            entry.sequence,
        )


operation_queue = OperationQueue()