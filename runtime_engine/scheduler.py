"""Deterministic schedule models and date calculations only."""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from core import AuraBaseModel, StorageError, ValidationError


class ScheduleFrequency(StrEnum):
    ONCE = "once"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


class RuntimeSchedule(AuraBaseModel):
    schedule_id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=250)
    frequency: ScheduleFrequency
    enabled: bool = True
    start_at: datetime
    interval: int = Field(default=1, ge=1)
    days_of_week: list[int] = Field(default_factory=list)
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_schedule(self) -> "RuntimeSchedule":
        for value in (self.start_at, self.last_run_at, self.next_run_at):
            if value is not None and (
                value.tzinfo is None or value.utcoffset() is None
            ):
                raise ValueError("Schedule timestamps must be timezone-aware.")
        if any(day < 0 or day > 6 for day in self.days_of_week):
            raise ValueError("days_of_week values must be between 0 and 6.")
        if self.frequency == ScheduleFrequency.WEEKLY and not self.days_of_week:
            raise ValueError("Weekly schedules require days_of_week.")
        if self.frequency != ScheduleFrequency.WEEKLY and self.days_of_week:
            raise ValueError("days_of_week is only valid for weekly schedules.")
        return self


class RuntimeScheduler:
    def __init__(self) -> None:
        self._schedules: dict[UUID, RuntimeSchedule] = {}

    def register_schedule(
        self, schedule: RuntimeSchedule, *, replace: bool = False
    ) -> RuntimeSchedule:
        if schedule.schedule_id in self._schedules and not replace:
            raise StorageError("Schedule is already registered.")
        schedule.next_run_at = self.calculate_next_run(schedule)
        self._schedules[schedule.schedule_id] = schedule
        return schedule

    def remove_schedule(self, schedule_id: UUID) -> RuntimeSchedule:
        try:
            return self._schedules.pop(schedule_id)
        except KeyError as error:
            raise ValidationError("Schedule was not found.") from error

    def enable_schedule(self, schedule_id: UUID) -> None:
        schedule = self._get(schedule_id)
        schedule.enabled = True
        schedule.next_run_at = self.calculate_next_run(schedule)

    def disable_schedule(self, schedule_id: UUID) -> None:
        schedule = self._get(schedule_id)
        schedule.enabled = False
        schedule.next_run_at = None

    def calculate_next_run(
        self,
        schedule: RuntimeSchedule,
        *,
        after: datetime | None = None,
    ) -> datetime | None:
        reference = after or schedule.last_run_at
        if reference is not None and (
            reference.tzinfo is None or reference.utcoffset() is None
        ):
            raise ValidationError("Calculation time must be timezone-aware.")
        if schedule.frequency == ScheduleFrequency.ONCE:
            if schedule.last_run_at is not None:
                return None
            return schedule.start_at
        reference = reference or schedule.start_at
        if schedule.frequency == ScheduleFrequency.HOURLY:
            return reference + timedelta(hours=schedule.interval)
        if schedule.frequency == ScheduleFrequency.DAILY:
            return reference + timedelta(days=schedule.interval)
        candidate = reference + timedelta(days=1)
        allowed = set(schedule.days_of_week)
        while candidate.weekday() not in allowed:
            candidate += timedelta(days=1)
        return candidate

    def mark_executed(self, schedule_id: UUID, executed_at: datetime) -> None:
        if executed_at.tzinfo is None or executed_at.utcoffset() is None:
            raise ValidationError("Execution time must be timezone-aware.")
        schedule = self._get(schedule_id)
        schedule.last_run_at = executed_at
        schedule.next_run_at = self.calculate_next_run(schedule)

    def list_schedules(self) -> tuple[RuntimeSchedule, ...]:
        return tuple(self._schedules.values())

    def due_schedules(self, at_time: datetime) -> tuple[RuntimeSchedule, ...]:
        if at_time.tzinfo is None or at_time.utcoffset() is None:
            raise ValidationError("Due time must be timezone-aware.")
        return tuple(
            schedule
            for schedule in self._schedules.values()
            if schedule.enabled
            and schedule.next_run_at is not None
            and schedule.next_run_at <= at_time
        )

    def _get(self, schedule_id: UUID) -> RuntimeSchedule:
        try:
            return self._schedules[schedule_id]
        except KeyError as error:
            raise ValidationError("Schedule was not found.") from error
