"""Unit tests for the SM-2 + learning-steps scheduler in app/services/srs.py."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.srs import (
    DEFAULT_EASE_FACTOR,
    EASY_INTERVAL_DAYS,
    GRADUATING_INTERVAL_DAYS,
    LEARNING_STEPS_MINUTES,
    MIN_EASE_FACTOR,
    Grade,
    Scheduling,
    SrsState,
    schedule,
)

NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def _new_card() -> SrsState:
    """A brand-new card: in learning at step 0."""
    return SrsState(repetitions=0, interval_days=0, ease_factor=DEFAULT_EASE_FACTOR, lapses=0)


def _review_card(interval_days: int = 30, ease: float = 2.5, lapses: int = 0) -> SrsState:
    """A graduated card in the review phase."""
    return SrsState(repetitions=5, interval_days=interval_days, ease_factor=ease, lapses=lapses)


def test_returns_scheduling() -> None:
    assert isinstance(schedule(_new_card(), Grade.good, now=NOW), Scheduling)


# --- Learning phase ---------------------------------------------------------


def test_new_card_good_advances_to_second_step_not_a_day() -> None:
    result = schedule(_new_card(), Grade.good, now=NOW)
    assert result.interval_days == 0  # still learning
    assert result.repetitions == 1  # advanced to step 1
    assert result.due_at == NOW + timedelta(minutes=LEARNING_STEPS_MINUTES[1])


def test_good_off_last_step_graduates_to_one_day() -> None:
    on_last_step = SrsState(
        repetitions=len(LEARNING_STEPS_MINUTES) - 1,
        interval_days=0,
        ease_factor=DEFAULT_EASE_FACTOR,
        lapses=0,
    )
    result = schedule(on_last_step, Grade.good, now=NOW)
    assert result.interval_days == GRADUATING_INTERVAL_DAYS
    assert result.due_at == NOW + timedelta(days=GRADUATING_INTERVAL_DAYS)


def test_again_while_learning_returns_to_first_step_soon() -> None:
    on_last_step = SrsState(repetitions=1, interval_days=0, ease_factor=2.5, lapses=3)
    result = schedule(on_last_step, Grade.again, now=NOW)
    assert result.interval_days == 0
    assert result.repetitions == 0
    assert result.due_at == NOW + timedelta(minutes=LEARNING_STEPS_MINUTES[0])
    # Failing a card that is still learning is not a lapse.
    assert result.lapses == 3


def test_easy_while_learning_graduates_immediately() -> None:
    result = schedule(_new_card(), Grade.easy, now=NOW)
    assert result.interval_days == EASY_INTERVAL_DAYS
    assert result.due_at == NOW + timedelta(days=EASY_INTERVAL_DAYS)


def test_learning_does_not_change_ease() -> None:
    for grade in Grade:
        result = schedule(_new_card(), grade, now=NOW)
        assert result.ease_factor == pytest.approx(DEFAULT_EASE_FACTOR)


# --- Review phase -----------------------------------------------------------


def test_good_review_multiplies_interval_by_ease() -> None:
    result = schedule(_review_card(interval_days=10, ease=2.5), Grade.good, now=NOW)
    assert result.interval_days == 25  # round(10 * 2.5)
    assert result.repetitions == 6
    assert result.ease_factor == pytest.approx(2.5)  # good leaves ease unchanged


def test_consecutive_good_reviews_grow_the_interval() -> None:
    state = _review_card(interval_days=1, ease=2.5, lapses=0)
    intervals = []
    for _ in range(4):
        result = schedule(state, Grade.good, now=NOW)
        intervals.append(result.interval_days)
        state = SrsState(
            repetitions=result.repetitions,
            interval_days=result.interval_days,
            ease_factor=result.ease_factor,
            lapses=result.lapses,
        )
    assert intervals == sorted(intervals) and intervals[0] < intervals[-1]


def test_again_in_review_is_a_lapse_into_relearning() -> None:
    result = schedule(_review_card(interval_days=30, ease=2.5, lapses=1), Grade.again, now=NOW)
    assert result.interval_days == 0  # back to (re)learning
    assert result.repetitions == 0
    assert result.lapses == 2  # lapse counted
    assert result.ease_factor == pytest.approx(2.3)  # 2.5 - 0.20
    assert result.due_at == NOW + timedelta(minutes=LEARNING_STEPS_MINUTES[0])


def test_easy_review_increases_ease_and_outpaces_good() -> None:
    easy = schedule(_review_card(interval_days=10, ease=2.5), Grade.easy, now=NOW)
    good = schedule(_review_card(interval_days=10, ease=2.5), Grade.good, now=NOW)
    assert easy.ease_factor > 2.5
    assert easy.interval_days > good.interval_days


def test_hard_review_decreases_ease() -> None:
    result = schedule(_review_card(interval_days=10, ease=2.5), Grade.hard, now=NOW)
    assert result.ease_factor == pytest.approx(2.35)  # 2.5 - 0.15
    assert result.repetitions == 6  # hard still counts as a review


def test_review_ease_never_drops_below_floor() -> None:
    result = schedule(_review_card(ease=MIN_EASE_FACTOR), Grade.again, now=NOW)
    assert result.ease_factor == pytest.approx(MIN_EASE_FACTOR)


# --- General properties -----------------------------------------------------


def test_is_pure_same_input_same_output() -> None:
    state = _review_card(interval_days=6, ease=2.5)
    assert schedule(state, Grade.good, now=NOW) == schedule(state, Grade.good, now=NOW)


def test_defaults_now_to_current_time() -> None:
    before = datetime.now(timezone.utc)
    result = schedule(_new_card(), Grade.good)
    after = datetime.now(timezone.utc)
    expected = timedelta(minutes=LEARNING_STEPS_MINUTES[1])
    assert before + expected <= result.due_at <= after + expected
