"""Integration tests for /api/auth endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError

from app.core.security import create_refresh_token, hash_password
from tests.conftest import make_session


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------


async def test_register_201(client_with_session: tuple[AsyncClient, AsyncMock]) -> None:
    ac, _ = client_with_session
    r = await ac.post(
        "/api/auth/register",
        json={"email": "new@example.com", "password": "strongpassword", "language": "jp"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["email"] == "new@example.com"
    assert data["language"] == "jp"
    assert "id" in data
    assert "created_at" in data


async def test_register_409_duplicate_email(client_with_session: tuple[AsyncClient, AsyncMock]) -> None:
    ac, sess = client_with_session
    sess.commit = AsyncMock(side_effect=IntegrityError(None, None, None))

    r = await ac.post(
        "/api/auth/register",
        json={"email": "dup@example.com", "password": "password123", "language": "cn"},
    )
    assert r.status_code == 409
    assert "already registered" in r.json()["detail"].lower()


async def test_register_422_invalid_email(client: AsyncClient) -> None:
    r = await client.post(
        "/api/auth/register",
        json={"email": "not-an-email", "password": "password123", "language": "jp"},
    )
    assert r.status_code == 422


async def test_register_422_invalid_language(client: AsyncClient) -> None:
    r = await client.post(
        "/api/auth/register",
        json={"email": "test@example.com", "password": "password123", "language": "fr"},
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


def _user_with_password(password: str) -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "test@example.com"
    user.hashed_password = hash_password(password)
    user.language = "jp"
    user.created_at = datetime.now(timezone.utc)
    return user


async def test_login_200_returns_access_token(client_with_session: tuple[AsyncClient, AsyncMock]) -> None:
    ac, sess = client_with_session
    mock_user = _user_with_password("secret123")

    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_user
    sess.execute = AsyncMock(return_value=result)

    r = await ac.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "secret123", "language": "jp"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


async def test_login_200_sets_refresh_cookie(client_with_session: tuple[AsyncClient, AsyncMock]) -> None:
    ac, sess = client_with_session
    mock_user = _user_with_password("secret123")

    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_user
    sess.execute = AsyncMock(return_value=result)

    r = await ac.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "secret123", "language": "jp"},
    )
    assert r.status_code == 200
    assert "refresh_token" in r.cookies


async def test_login_401_user_not_found(client_with_session: tuple[AsyncClient, AsyncMock]) -> None:
    ac, sess = client_with_session
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    sess.execute = AsyncMock(return_value=result)

    r = await ac.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "secret123", "language": "jp"},
    )
    assert r.status_code == 401


async def test_login_401_wrong_password(client_with_session: tuple[AsyncClient, AsyncMock]) -> None:
    ac, sess = client_with_session
    mock_user = _user_with_password("correctpassword")

    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_user
    sess.execute = AsyncMock(return_value=result)

    r = await ac.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "wrongpassword", "language": "jp"},
    )
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------


async def test_refresh_200_returns_new_access_token(
    client_with_session: tuple[AsyncClient, AsyncMock]
) -> None:
    ac, sess = client_with_session
    user_id = str(uuid.uuid4())

    mock_user = MagicMock()
    mock_user.id = user_id
    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_user
    sess.execute = AsyncMock(return_value=result)

    refresh_tok = create_refresh_token(user_id)
    ac.cookies.set("refresh_token", refresh_tok)

    r = await ac.post("/api/auth/refresh")
    assert r.status_code == 200
    assert "access_token" in r.json()


async def test_refresh_401_missing_cookie(client: AsyncClient) -> None:
    r = await client.post("/api/auth/refresh")
    assert r.status_code == 401


async def test_refresh_401_invalid_token(client: AsyncClient) -> None:
    client.cookies.set("refresh_token", "not.a.valid.token")
    r = await client.post("/api/auth/refresh")
    assert r.status_code == 401


async def test_refresh_401_access_token_used_as_refresh(
    client_with_session: tuple[AsyncClient, AsyncMock]
) -> None:
    from app.core.security import create_access_token

    ac, _ = client_with_session
    # Sending an access token where a refresh token is expected
    access_tok = create_access_token(str(uuid.uuid4()))
    ac.cookies.set("refresh_token", access_tok)

    r = await ac.post("/api/auth/refresh")
    assert r.status_code == 401
