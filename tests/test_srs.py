"""Unit tests for the pure SM-2 scheduler in app/services/srs.py."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.srs import (
    DEFAULT_EASE_FACTOR,
    MIN_EASE_FACTOR,
    Grade,
    Scheduling,
    SrsState,
    schedule,
)

NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def _new_card() -> SrsState:
    return SrsState(repetitions=0, interval_days=0, ease_factor=DEFAULT_EASE_FACTOR, lapses=0)


def test_returns_scheduling_with_due_in_interval_days() -> None:
    result = schedule(_new_card(), Grade.good, now=NOW)
    assert isinstance(result, Scheduling)
    assert result.due_at == NOW + timedelta(days=result.interval_days)


def test_first_good_review_is_one_day() -> None:
    result = schedule(_new_card(), Grade.good, now=NOW)
    assert result.interval_days == 1
    assert result.repetitions == 1


def test_second_good_review_is_six_days() -> None:
    after_first = SrsState(
        repetitions=1, interval_days=1, ease_factor=DEFAULT_EASE_FACTOR, lapses=0
    )
    result = schedule(after_first, Grade.good, now=NOW)
    assert result.interval_days == 6
    assert result.repetitions == 2


def test_third_good_review_multiplies_interval_by_ease() -> None:
    mature = SrsState(repetitions=2, interval_days=6, ease_factor=2.5, lapses=0)
    result = schedule(mature, Grade.good, now=NOW)
    assert result.interval_days == round(6 * 2.5)  # 15
    assert result.repetitions == 3


def test_again_is_a_lapse_that_resets_streak() -> None:
    mature = SrsState(repetitions=4, interval_days=30, ease_factor=2.5, lapses=1)
    result = schedule(mature, Grade.again, now=NOW)
    assert result.repetitions == 0
    assert result.interval_days == 1
    assert result.lapses == 2


def test_good_does_not_change_ease() -> None:
    result = schedule(_new_card(), Grade.good, now=NOW)
    assert result.ease_factor == pytest.approx(DEFAULT_EASE_FACTOR)


def test_easy_increases_ease() -> None:
    result = schedule(_new_card(), Grade.easy, now=NOW)
    assert result.ease_factor > DEFAULT_EASE_FACTOR


def test_hard_decreases_ease_but_still_passes() -> None:
    result = schedule(_new_card(), Grade.hard, now=NOW)
    assert result.ease_factor < DEFAULT_EASE_FACTOR
    assert result.repetitions == 1  # hard is still a passing grade


def test_ease_never_drops_below_floor() -> None:
    fragile = SrsState(repetitions=0, interval_days=0, ease_factor=MIN_EASE_FACTOR, lapses=0)
    result = schedule(fragile, Grade.again, now=NOW)
    assert result.ease_factor == pytest.approx(MIN_EASE_FACTOR)


def test_is_pure_same_input_same_output() -> None:
    state = SrsState(repetitions=2, interval_days=6, ease_factor=2.5, lapses=0)
    assert schedule(state, Grade.good, now=NOW) == schedule(state, Grade.good, now=NOW)


def test_defaults_now_to_current_time() -> None:
    before = datetime.now(timezone.utc)
    result = schedule(_new_card(), Grade.good)
    after = datetime.now(timezone.utc)
    assert before + timedelta(days=1) <= result.due_at <= after + timedelta(days=1)
