"""Integration tests for /api/review endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient


def _mock_card(user_id: uuid.UUID, **overrides: object) -> MagicMock:
    card = MagicMock()
    card.id = uuid.uuid4()
    card.user_id = user_id
    card.language = "jp"
    card.expression = "食べる"
    card.reading = "たべる"
    card.meaning = "to eat"
    card.jlpt_level = 5
    card.hsk_level = None
    card.status = "new"
    card.due_at = datetime.now(timezone.utc)
    card.interval_days = 0
    card.ease_factor = 2.5
    card.repetitions = 0
    card.lapses = 0
    card.last_reviewed_at = None
    card.first_reviewed_at = None
    card.suspended = False
    for key, value in overrides.items():
        setattr(card, key, value)
    return card


def _scalars_returning(*cards: object) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = list(cards)
    return result


def _count_returning(n: int) -> MagicMock:
    result = MagicMock()
    result.scalar_one.return_value = n
    return result


# ---------------------------------------------------------------------------
# GET /api/review/queue
# ---------------------------------------------------------------------------


async def test_queue_requires_language(authed_client: AsyncClient) -> None:
    r = await authed_client.get("/api/review/queue")
    assert r.status_code == 422


async def test_queue_empty_returns_empty_list(authed_client: AsyncClient) -> None:
    r = await authed_client.get("/api/review/queue?language=jp")
    assert r.status_code == 200
    assert r.json() == []


async def test_queue_403_unauthenticated(client: AsyncClient) -> None:
    r = await client.get("/api/review/queue?language=jp")
    assert r.status_code == 403


async def test_queue_returns_due_then_new(
    authed_client_with_session: tuple[AsyncClient, AsyncMock],
    test_user: MagicMock,
) -> None:
    ac, sess = authed_client_with_session
    due = _mock_card(
        test_user.id,
        last_reviewed_at=datetime.now(timezone.utc) - timedelta(days=2),
        repetitions=3,
    )
    new = _mock_card(test_user.id, last_reviewed_at=None)
    # execute() order: due query, count of today's introductions, new-cards query.
    sess.execute = AsyncMock(
        side_effect=[_scalars_returning(due), _count_returning(0), _scalars_returning(new)]
    )

    r = await ac.get("/api/review/queue?language=jp&limit=20")
    assert r.status_code == 200
    ids = [c["id"] for c in r.json()]
    assert ids == [str(due.id), str(new.id)]


async def test_queue_daily_cap_excludes_new_when_reached(
    authed_client_with_session: tuple[AsyncClient, AsyncMock],
) -> None:
    ac, sess = authed_client_with_session
    # No due cards; the daily new-card limit (5) is already used up today (5).
    # The new-cards query must therefore never run (no third execute result).
    sess.execute = AsyncMock(side_effect=[_scalars_returning(), _count_returning(5)])

    r = await ac.get("/api/review/queue?language=jp&new_per_day=5")
    assert r.status_code == 200
    assert r.json() == []


async def test_queue_new_per_day_zero_serves_no_new(
    authed_client_with_session: tuple[AsyncClient, AsyncMock],
    test_user: MagicMock,
) -> None:
    ac, sess = authed_client_with_session
    # Even with new cards available, new_per_day=0 must skip the new-cards query.
    sess.execute = AsyncMock(side_effect=[_scalars_returning(), _count_returning(0)])

    r = await ac.get("/api/review/queue?language=jp&new_per_day=0")
    assert r.status_code == 200
    assert r.json() == []


# ---------------------------------------------------------------------------
# POST /api/review/{id} — grade
# ---------------------------------------------------------------------------


async def test_grade_404_when_missing(authed_client: AsyncClient) -> None:
    r = await authed_client.post(f"/api/review/{uuid.uuid4()}", json={"grade": "good"})
    assert r.status_code == 404


async def test_grade_403_when_not_owner(
    authed_client_with_session: tuple[AsyncClient, AsyncMock],
) -> None:
    ac, sess = authed_client_with_session
    someone_else = _mock_card(uuid.uuid4())
    result = MagicMock()
    result.scalar_one_or_none.return_value = someone_else
    sess.execute = AsyncMock(return_value=result)

    r = await ac.post(f"/api/review/{someone_else.id}", json={"grade": "good"})
    assert r.status_code == 403


async def test_grade_invalid_grade_422(
    authed_client: AsyncClient,
) -> None:
    r = await authed_client.post(f"/api/review/{uuid.uuid4()}", json={"grade": "perfect"})
    assert r.status_code == 422


async def test_grade_good_persists_and_returns_result(
    authed_client_with_session: tuple[AsyncClient, AsyncMock],
    test_user: MagicMock,
) -> None:
    ac, sess = authed_client_with_session
    card = _mock_card(test_user.id)
    result = MagicMock()
    result.scalar_one_or_none.return_value = card
    sess.execute = AsyncMock(return_value=result)

    r = await ac.post(f"/api/review/{card.id}", json={"grade": "good"})
    assert r.status_code == 200
    body = r.json()
    # A brand-new card answered "good" advances a learning step (sub-day), so it
    # stays at interval_days 0 but its due date is pushed into the future.
    assert body["interval_days"] == 0
    assert body["repetitions"] == 1
    assert datetime.fromisoformat(body["due_at"]) > datetime.now(timezone.utc)
    assert card.last_reviewed_at is not None
    assert card.first_reviewed_at is not None  # stamped on first review
    sess.commit.assert_awaited()


# ---------------------------------------------------------------------------
# GET /api/review/stats
# ---------------------------------------------------------------------------


async def test_stats_returns_counts(
    authed_client_with_session: tuple[AsyncClient, AsyncMock],
) -> None:
    ac, sess = authed_client_with_session
    result = MagicMock()
    result.mappings.return_value.one.return_value = {
        "new": 3,
        "due": 5,
        "learned": 7,
        "suspended": 2,
    }
    sess.execute = AsyncMock(return_value=result)

    r = await ac.get("/api/review/stats?language=jp")
    assert r.status_code == 200
    assert r.json() == {"new": 3, "due": 5, "learned": 7, "suspended": 2}


# ---------------------------------------------------------------------------
# POST /api/review/{id}/suspend + /unsuspend
# ---------------------------------------------------------------------------


async def test_suspend_sets_flag(
    authed_client_with_session: tuple[AsyncClient, AsyncMock],
    test_user: MagicMock,
) -> None:
    ac, sess = authed_client_with_session
    card = _mock_card(test_user.id, suspended=False)
    result = MagicMock()
    result.scalar_one_or_none.return_value = card
    sess.execute = AsyncMock(return_value=result)

    r = await ac.post(f"/api/review/{card.id}/suspend")
    assert r.status_code == 200
    assert card.suspended is True


async def test_unsuspend_clears_flag(
    authed_client_with_session: tuple[AsyncClient, AsyncMock],
    test_user: MagicMock,
) -> None:
    ac, sess = authed_client_with_session
    card = _mock_card(test_user.id, suspended=True)
    result = MagicMock()
    result.scalar_one_or_none.return_value = card
    sess.execute = AsyncMock(return_value=result)

    r = await ac.post(f"/api/review/{card.id}/unsuspend")
    assert r.status_code == 200
    assert card.suspended is False
