"""Spaced-repetition scheduling (SM-2).

A pure, DB-free implementation of the SuperMemo SM-2 algorithm so it stays
trivially unit-testable. The router reads SRS state off a SavedWord, calls
``schedule``, and writes the returned values back. Nothing here touches the
database or the ORM.

Reference: https://super-memory.com/english/ol/sm2.htm
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

# SM-2 never lets the ease factor drop below this floor.
MIN_EASE_FACTOR = 1.3
# Ease factor a brand-new card starts at (mirrors the column default).
DEFAULT_EASE_FACTOR = 2.5


class Grade(str, enum.Enum):
    """How well the user recalled a card. Maps to an SM-2 quality score."""

    again = "again"  # failed — forgot the card
    hard = "hard"  # recalled with serious difficulty
    good = "good"  # recalled correctly
    easy = "easy"  # recalled effortlessly


# SM-2 quality scale is 0–5; we expose four buttons and map them onto the
# passing/failing halves of that scale. quality < 3 is a lapse.
_QUALITY: dict[Grade, int] = {
    Grade.again: 2,
    Grade.hard: 3,
    Grade.good: 4,
    Grade.easy: 5,
}


@dataclass(frozen=True)
class SrsState:
    """The SM-2 fields of a card before review."""

    repetitions: int
    interval_days: int
    ease_factor: float
    lapses: int


@dataclass(frozen=True)
class Scheduling:
    """The SM-2 fields of a card after review, plus the next due date."""

    repetitions: int
    interval_days: int
    ease_factor: float
    lapses: int
    due_at: datetime


def schedule(state: SrsState, grade: Grade, *, now: datetime | None = None) -> Scheduling:
    """Apply one SM-2 review to ``state`` and return the next scheduling.

    Pure function: given the same inputs it always returns the same output.
    ``now`` is injectable for deterministic tests; it defaults to the current
    UTC time. Returns a Scheduling with the updated repetitions, interval_days,
    ease_factor, lapses and the absolute due_at.
    """
    now = now or datetime.now(UTC)
    quality = _QUALITY[grade]

    repetitions = state.repetitions
    lapses = state.lapses

    if quality < 3:
        # Lapse: reset the repetition streak and re-learn from a 1-day interval.
        repetitions = 0
        interval_days = 1
        lapses += 1
    else:
        if repetitions == 0:
            interval_days = 1
        elif repetitions == 1:
            interval_days = 6
        else:
            interval_days = round(state.interval_days * state.ease_factor)
        repetitions += 1

    # SM-2 ease adjustment, clamped to the floor.
    ease_factor = state.ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    ease_factor = max(MIN_EASE_FACTOR, ease_factor)

    due_at = now + timedelta(days=interval_days)
    return Scheduling(
        repetitions=repetitions,
        interval_days=interval_days,
        ease_factor=ease_factor,
        lapses=lapses,
        due_at=due_at,
    )
