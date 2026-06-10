"""Spaced-repetition scheduling: SM-2 with Anki-style learning steps.

A pure, DB-free scheduler so it stays trivially unit-testable. The router reads
SRS state off a SavedWord, calls ``schedule``, and writes the returned values
back. Nothing here touches the database or the ORM.

Two phases, distinguished by ``interval_days``:

* **Learning / relearning** (``interval_days == 0``) — the card is stepped
  through short, sub-day intervals (``LEARNING_STEPS_MINUTES``). ``repetitions``
  holds the current step index. ``again`` drops back to the first step so the
  card resurfaces within the same session (this is the behaviour plain SM-2
  lacks). Ease is left untouched while learning.
* **Review** (``interval_days >= 1``) — graduated cards scheduled in whole days
  via the classic SM-2 ``interval * ease_factor`` growth. ``again`` here is a
  true lapse: it lowers ease, increments ``lapses`` and sends the card back into
  relearning.

Because intervals can be sub-day, the authoritative "next time" is always
``due_at``; ``interval_days`` is 0 for anything still in (re)learning.

Reference: https://super-memory.com/english/ol/sm2.htm (SM-2) plus Anki's
learning-steps model layered on top.
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

# --- Tunables ---------------------------------------------------------------
# Sub-day steps a card walks through before graduating. "again" restarts at the
# first step, so a lapsed/forgotten card comes back almost immediately.
LEARNING_STEPS_MINUTES = (1, 10)
# Interval a card graduates to on "good" out of the last learning step.
GRADUATING_INTERVAL_DAYS = 1
# Interval a card jumps straight to when answered "easy" while learning.
EASY_INTERVAL_DAYS = 4
# Review-phase interval multipliers.
HARD_INTERVAL_FACTOR = 1.2
EASY_BONUS = 1.3
# Ease bounds. SM-2 never lets ease drop below the floor.
MIN_EASE_FACTOR = 1.3
DEFAULT_EASE_FACTOR = 2.5


class Grade(str, enum.Enum):
    """How well the user recalled a card."""

    again = "again"  # failed — forgot the card
    hard = "hard"  # recalled with serious difficulty
    good = "good"  # recalled correctly
    easy = "easy"  # recalled effortlessly


# Ease adjustment applied only in the review phase (learning never touches ease).
_REVIEW_EASE_DELTA: dict[Grade, float] = {
    Grade.again: -0.20,
    Grade.hard: -0.15,
    Grade.good: 0.0,
    Grade.easy: 0.15,
}


@dataclass(frozen=True)
class SrsState:
    """The scheduling fields of a card before review.

    ``interval_days == 0`` means the card is in learning/relearning and
    ``repetitions`` is its current learning-step index; otherwise the card is in
    the review phase and ``repetitions`` counts successful reviews.
    """

    repetitions: int
    interval_days: int
    ease_factor: float
    lapses: int


@dataclass(frozen=True)
class Scheduling:
    """The scheduling fields of a card after review, plus the next due date."""

    repetitions: int
    interval_days: int
    ease_factor: float
    lapses: int
    due_at: datetime


def schedule(state: SrsState, grade: Grade, *, now: datetime | None = None) -> Scheduling:
    """Apply one review to ``state`` and return the next scheduling.

    Pure function: identical inputs always yield identical output. ``now`` is
    injectable for deterministic tests, defaulting to the current UTC time.
    Dispatches to the learning or review machine based on ``interval_days``.
    """
    now = now or datetime.now(UTC)
    if state.interval_days >= 1:
        return _schedule_review(state, grade, now)
    return _schedule_learning(state, grade, now)


def project_intervals(state: SrsState) -> dict[Grade, int]:
    """Seconds-until-due for each grade if applied to ``state`` now, without persisting.

    Lets the client preview the next interval on each grade button. The delta is
    independent of the reference instant, so a fixed epoch is used. Sub-day
    (learning) grades yield small values; review grades yield multi-day values.
    """
    ref = datetime(2000, 1, 1, tzinfo=UTC)
    return {
        grade: int((schedule(state, grade, now=ref).due_at - ref).total_seconds())
        for grade in Grade
    }


def _schedule_learning(state: SrsState, grade: Grade, now: datetime) -> Scheduling:
    """Step a learning/relearning card; ease is left unchanged here."""
    steps = LEARNING_STEPS_MINUTES

    if grade is Grade.again:
        return _after_minutes(state, repetitions=0, minutes=steps[0], now=now)

    if grade is Grade.hard:
        # Repeat the current step rather than advancing.
        step = max(0, min(state.repetitions, len(steps) - 1))
        return _after_minutes(state, repetitions=step, minutes=steps[step], now=now)

    if grade is Grade.easy:
        # Skip the remaining steps and graduate with the longer easy interval.
        return _graduate(state, EASY_INTERVAL_DAYS, now)

    # Grade.good: advance one step, graduating off the end.
    next_step = state.repetitions + 1
    if next_step >= len(steps):
        return _graduate(state, GRADUATING_INTERVAL_DAYS, now)
    return _after_minutes(state, repetitions=next_step, minutes=steps[next_step], now=now)


def _schedule_review(state: SrsState, grade: Grade, now: datetime) -> Scheduling:
    """Reschedule a graduated card; ``again`` lapses it back into relearning."""
    ease = max(MIN_EASE_FACTOR, state.ease_factor + _REVIEW_EASE_DELTA[grade])

    if grade is Grade.again:
        # Lapse: lower ease, count it, and drop into relearning at the first step.
        return Scheduling(
            repetitions=0,
            interval_days=0,
            ease_factor=ease,
            lapses=state.lapses + 1,
            due_at=now + timedelta(minutes=LEARNING_STEPS_MINUTES[0]),
        )

    if grade is Grade.hard:
        interval_days = _grow(state.interval_days, HARD_INTERVAL_FACTOR)
    elif grade is Grade.easy:
        interval_days = _grow(state.interval_days, state.ease_factor * EASY_BONUS)
    else:  # Grade.good
        interval_days = _grow(state.interval_days, state.ease_factor)

    return Scheduling(
        repetitions=state.repetitions + 1,
        interval_days=interval_days,
        ease_factor=ease,
        lapses=state.lapses,
        due_at=now + timedelta(days=interval_days),
    )


def _graduate(state: SrsState, interval_days: int, now: datetime) -> Scheduling:
    """Move a learning card into the review phase at ``interval_days``."""
    return Scheduling(
        repetitions=1,
        interval_days=interval_days,
        ease_factor=state.ease_factor,
        lapses=state.lapses,
        due_at=now + timedelta(days=interval_days),
    )


def _after_minutes(state: SrsState, *, repetitions: int, minutes: int, now: datetime) -> Scheduling:
    """Keep a card in learning, due ``minutes`` from now, ease untouched."""
    return Scheduling(
        repetitions=repetitions,
        interval_days=0,
        ease_factor=state.ease_factor,
        lapses=state.lapses,
        due_at=now + timedelta(minutes=minutes),
    )


def _grow(interval_days: int, factor: float) -> int:
    """Multiply an interval, rounding to whole days and always growing by >=1."""
    return max(interval_days + 1, math.floor(interval_days * factor + 0.5))
