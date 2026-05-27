"""Shared fixtures for all test modules."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.deps import get_current_user
from app.core.rate_limit import get_redis
from app.db.database import get_session
from app.main import app
from app.models.user import LanguageEnum


def make_session() -> AsyncMock:
    """Return a fully-wired AsyncSession mock that simulates an empty database."""
    session = AsyncMock()

    result = MagicMock()
    result.mappings.return_value.all.return_value = []
    result.mappings.return_value.first.return_value = None
    result.scalar_one.return_value = 0
    result.scalar_one_or_none.return_value = None
    result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.delete = AsyncMock()
    session.rollback = AsyncMock()
    session.get = AsyncMock(return_value=None)

    async def _refresh(obj: object) -> None:
        if not getattr(obj, "id", None):
            try:
                obj.id = uuid.uuid4()  # type: ignore[attr-defined]
            except AttributeError:
                pass
        for field in ("added_at", "searched_at", "created_at"):
            if not getattr(obj, field, None):
                try:
                    setattr(obj, field, datetime.now(timezone.utc))
                except AttributeError:
                    pass

    session.refresh = AsyncMock(side_effect=_refresh)
    return session


def make_redis(counter_start: int = 0) -> AsyncMock:
    """Return a Redis mock; counter_start lets tests pre-fill the rate counter."""
    state = {"count": counter_start}
    redis = AsyncMock()

    async def _incr(key: str) -> int:
        state["count"] += 1
        return state["count"]

    redis.incr = AsyncMock(side_effect=_incr)
    redis.expire = AsyncMock()
    redis.aclose = AsyncMock()
    return redis


# ---------------------------------------------------------------------------
# Reusable fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_redis():
    """Mock Redis for every test to prevent real rate-limit state from leaking.

    test_injection.py defines its own client fixture that calls
    app.dependency_overrides.clear() on teardown, which removes this override;
    the pop() below is therefore a safe no-op for those tests.
    """
    redis = make_redis()
    app.dependency_overrides[get_redis] = lambda: redis
    yield
    app.dependency_overrides.pop(get_redis, None)


@pytest.fixture
def test_user() -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "test@example.com"
    user.language = LanguageEnum.jp
    user.hashed_password = ""
    return user


@pytest.fixture
async def client():
    """Basic client — DB and Redis mocked, no auth override."""
    sess = make_session()
    redis = make_redis()

    async def _session():
        yield sess

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_redis] = lambda: redis
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def client_with_session():
    """Yields (AsyncClient, session mock) so tests can configure session behaviour."""
    sess = make_session()
    redis = make_redis()

    async def _session():
        yield sess

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_redis] = lambda: redis
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac, sess
    app.dependency_overrides.clear()


@pytest.fixture
async def authed_client(test_user: MagicMock):
    """Client with get_current_user overridden to return test_user."""
    sess = make_session()
    redis = make_redis()

    async def _session():
        yield sess

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_redis] = lambda: redis
    app.dependency_overrides[get_current_user] = lambda: test_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def authed_client_with_session(test_user: MagicMock):
    """Yields (AsyncClient, session mock) with auth override in place."""
    sess = make_session()
    redis = make_redis()

    async def _session():
        yield sess

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_redis] = lambda: redis
    app.dependency_overrides[get_current_user] = lambda: test_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac, sess
    app.dependency_overrides.clear()
