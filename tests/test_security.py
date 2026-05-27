"""Verification tests for 9.15: security headers, CORS, and rate limiting."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.rate_limit import get_redis
from app.db.database import get_session
from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session() -> AsyncMock:
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
    session.refresh = AsyncMock()
    return session


def _make_redis(counter_start: int = 0) -> AsyncMock:
    """Redis mock with a shared per-fixture counter."""
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
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def client():
    """Basic client — Redis is not mocked so rate_limit fails open."""
    sess = _make_session()
    async def _session(): yield sess
    app.dependency_overrides[get_session] = _session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def _rate_limited_fixtures(counter_start: int):
    """Factory: fixture whose Redis counter starts at counter_start."""
    @pytest.fixture
    async def _fixture():
        sess = _make_session()
        redis = _make_redis(counter_start)
        async def _session(): yield sess
        app.dependency_overrides[get_session] = _session
        app.dependency_overrides[get_redis] = lambda: redis
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
        app.dependency_overrides.clear()
    return _fixture


# counter at 59 → next incr = 60 → exactly at limit → allowed
under_limit_client = _rate_limited_fixtures(59)

# counter at 60 → next incr = 61 → over limit → 429
over_limit_client = _rate_limited_fixtures(60)


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------


async def test_security_headers_on_health(client: AsyncClient) -> None:
    r = await client.get("/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Referrer-Policy"] == "no-referrer"


async def test_security_headers_on_search_response(client: AsyncClient) -> None:
    r = await client.get("/api/search", params={"q": "test", "lang": "jp"})
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("Referrer-Policy") == "no-referrer"


async def test_security_headers_on_error_response(client: AsyncClient) -> None:
    r = await client.get("/api/search", params={"q": " ", "lang": "jp"})
    assert r.status_code == 422
    assert r.headers.get("X-Content-Type-Options") == "nosniff"


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------


async def test_cors_unknown_origin_gets_no_allow_header(client: AsyncClient) -> None:
    r = await client.get("/health", headers={"Origin": "https://evil.example.com"})
    assert "access-control-allow-origin" not in r.headers


async def test_cors_known_origin_gets_allow_header(client: AsyncClient) -> None:
    r = await client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"


async def test_cors_preflight_unknown_origin_rejected(client: AsyncClient) -> None:
    r = await client.options(
        "/api/search",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in r.headers


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------


async def test_rate_limit_allows_request_at_threshold(
    under_limit_client: AsyncClient,
) -> None:
    r = await under_limit_client.get("/api/search", params={"q": "test", "lang": "jp"})
    assert r.status_code != 429


async def test_rate_limit_returns_429_over_threshold(
    over_limit_client: AsyncClient,
) -> None:
    r = await over_limit_client.get("/api/search", params={"q": "test", "lang": "jp"})
    assert r.status_code == 429
    assert r.headers.get("Retry-After") == "60"


async def test_rate_limit_429_has_retry_after_header(
    over_limit_client: AsyncClient,
) -> None:
    r = await over_limit_client.get("/api/kanji/search", params={"value": "test"})
    assert r.status_code == 429
    assert r.headers["Retry-After"] == "60"


async def test_rate_limit_429_on_analyze(
    over_limit_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.routers.analyze.tokenize_japanese", lambda q: [])
    monkeypatch.setattr("app.routers.analyze.tokenize_chinese", lambda q: [])
    r = await over_limit_client.post(
        "/api/analyze", json={"query": "test", "language": "jp"}
    )
    assert r.status_code == 429
