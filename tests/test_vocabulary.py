"""Integration tests for /api/vocabulary endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError

from tests.conftest import make_session

_WORD_PAYLOAD = {
    "language": "jp",
    "expression": "食べる",
    "reading": "たべる",
    "meaning": "to eat",
    "jlpt_level": 5,
    "status": "new",
}


def _mock_word(user_id: uuid.UUID) -> MagicMock:
    word = MagicMock()
    word.id = uuid.uuid4()
    word.user_id = user_id
    word.language = "jp"
    word.expression = "食べる"
    word.reading = "たべる"
    word.meaning = "to eat"
    word.jlpt_level = 5
    word.hsk_level = None
    word.status = "new"
    word.added_at = datetime.now(timezone.utc)
    return word


# ---------------------------------------------------------------------------
# GET /api/vocabulary — list
# ---------------------------------------------------------------------------


async def test_list_vocabulary_200(authed_client: AsyncClient) -> None:
    r = await authed_client.get("/api/vocabulary")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_list_vocabulary_returns_empty_list_when_no_words(authed_client: AsyncClient) -> None:
    r = await authed_client.get("/api/vocabulary")
    assert r.json() == []


async def test_list_vocabulary_403_unauthenticated(client: AsyncClient) -> None:
    r = await client.get("/api/vocabulary")
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# POST /api/vocabulary — add
# ---------------------------------------------------------------------------


async def test_add_vocabulary_201(
    authed_client_with_session: tuple[AsyncClient, AsyncMock],
    test_user: MagicMock,
) -> None:
    ac, sess = authed_client_with_session
    word = _mock_word(test_user.id)

    async def _refresh(obj):
        obj.id = word.id
        obj.added_at = word.added_at
        obj.user_id = test_user.id
        obj.language = "jp"
        obj.expression = "食べる"
        obj.reading = "たべる"
        obj.meaning = "to eat"
        obj.jlpt_level = 5
        obj.hsk_level = None
        obj.status = "new"

    sess.refresh = AsyncMock(side_effect=_refresh)

    r = await ac.post("/api/vocabulary", json=_WORD_PAYLOAD)
    assert r.status_code == 201


async def test_add_vocabulary_409_duplicate(
    authed_client_with_session: tuple[AsyncClient, AsyncMock],
) -> None:
    ac, sess = authed_client_with_session
    sess.commit = AsyncMock(side_effect=IntegrityError(None, None, None))

    r = await ac.post("/api/vocabulary", json=_WORD_PAYLOAD)
    assert r.status_code == 409
    assert "already saved" in r.json()["detail"].lower()


async def test_add_vocabulary_403_unauthenticated(client: AsyncClient) -> None:
    r = await client.post("/api/vocabulary", json=_WORD_PAYLOAD)
    assert r.status_code == 403


async def test_add_vocabulary_422_expression_too_long(authed_client: AsyncClient) -> None:
    payload = {**_WORD_PAYLOAD, "expression": "x" * 101}
    r = await authed_client.post("/api/vocabulary", json=payload)
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /api/vocabulary/{id} — delete own word
# ---------------------------------------------------------------------------


async def test_delete_own_word_204(
    authed_client_with_session: tuple[AsyncClient, AsyncMock],
    test_user: MagicMock,
) -> None:
    ac, sess = authed_client_with_session
    word = _mock_word(test_user.id)

    result = MagicMock()
    result.scalar_one_or_none.return_value = word
    sess.execute = AsyncMock(return_value=result)

    r = await ac.delete(f"/api/vocabulary/{word.id}")
    assert r.status_code == 204


async def test_delete_other_users_word_403(
    authed_client_with_session: tuple[AsyncClient, AsyncMock],
) -> None:
    ac, sess = authed_client_with_session
    # Word belongs to a *different* user_id
    other_user_id = uuid.uuid4()
    word = _mock_word(other_user_id)

    result = MagicMock()
    result.scalar_one_or_none.return_value = word
    sess.execute = AsyncMock(return_value=result)

    r = await ac.delete(f"/api/vocabulary/{word.id}")
    assert r.status_code == 403


async def test_delete_nonexistent_word_404(
    authed_client_with_session: tuple[AsyncClient, AsyncMock],
) -> None:
    ac, sess = authed_client_with_session

    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    sess.execute = AsyncMock(return_value=result)

    r = await ac.delete(f"/api/vocabulary/{uuid.uuid4()}")
    assert r.status_code == 404


async def test_delete_word_403_unauthenticated(client: AsyncClient) -> None:
    r = await client.delete(f"/api/vocabulary/{uuid.uuid4()}")
    assert r.status_code == 403
