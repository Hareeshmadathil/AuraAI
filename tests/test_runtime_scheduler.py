"""Tests for deterministic runtime schedule calculations."""

from datetime import UTC, datetime, timedelta

import pytest

from runtime_engine.scheduler import (
    RuntimeSchedule,
    RuntimeScheduler,
    ScheduleFrequency,
)


BASE = datetime(2026, 7, 13, 9, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("frequency", "expected"),
    [
        (ScheduleFrequency.ONCE, BASE),
        (ScheduleFrequency.HOURLY, BASE + timedelta(hours=1)),
        (ScheduleFrequency.DAILY, BASE + timedelta(days=1)),
    ],
)
def test_next_run_calculations(frequency, expected) -> None:
    scheduler = RuntimeScheduler()
    schedule = RuntimeSchedule(
        name="Test schedule",
        frequency=frequency,
        start_at=BASE,
    )
    assert scheduler.calculate_next_run(schedule) == expected


def test_weekly_due_enable_disable_and_execution() -> None:
    scheduler = RuntimeScheduler()
    schedule = RuntimeSchedule(
        name="Weekly schedule",
        frequency=ScheduleFrequency.WEEKLY,
        start_at=BASE,
        days_of_week=[1],
    )
    scheduler.register_schedule(schedule)
    assert schedule.next_run_at == BASE + timedelta(days=1)
    assert scheduler.due_schedules(BASE + timedelta(days=1)) == (schedule,)
    scheduler.disable_schedule(schedule.schedule_id)
    assert scheduler.due_schedules(BASE + timedelta(days=2)) == ()
    scheduler.enable_schedule(schedule.schedule_id)
    scheduler.mark_executed(schedule.schedule_id, BASE + timedelta(days=1))
    assert schedule.last_run_at == BASE + timedelta(days=1)
    assert scheduler.remove_schedule(schedule.schedule_id) is schedule


def test_invalid_schedule_validation() -> None:
    with pytest.raises(ValueError):
        RuntimeSchedule(
            name="Naive",
            frequency=ScheduleFrequency.ONCE,
            start_at=datetime(2026, 1, 1),
        )
    with pytest.raises(ValueError):
        RuntimeSchedule(
            name="Weekly",
            frequency=ScheduleFrequency.WEEKLY,
            start_at=BASE,
        )
