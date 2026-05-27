"""Injection and input-validation tests for every public endpoint.

For each endpoint: null bytes and whitespace-only inputs must be rejected
with 422; SQL/XSS payloads must never produce a 500 response.
"""
from __future__ import annotations

import urllib.parse
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.deps import get_current_user
from app.db.database import get_session
from app.main import app

# ---------------------------------------------------------------------------
# Payload sets
# ---------------------------------------------------------------------------

INJECTION_PAYLOADS = [
    "' OR '1'='1",
    "' OR 1=1--",
    "'; DROP TABLE users;--",
    "1; SELECT * FROM users--",
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
]

# After null-byte stripping these become blank → 422
BLANK_AFTER_STRIP_PAYLOADS = ["\x00", "\x00\x00"]

# After null-byte stripping these are still valid strings → not 500
SANITIZED_PAYLOADS = ["a\x00b", "test\x00query"]

BLANK_PAYLOADS = ["   ", "\t\n", " \r\n "]

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_session() -> AsyncMock:
    """AsyncSession mock that returns empty results and refreshes ORM objects."""
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
    session.get = AsyncMock(return_value=None)

    async def _refresh(obj: object) -> None:
        """Set auto-generated DB fields that the handler reads after refresh."""
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


@pytest.fixture
async def client():
    """HTTP client with DB mocked out; no auth."""
    sess = _make_session()

    async def _session():
        yield sess

    app.dependency_overrides[get_session] = _session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def authed_client():
    """HTTP client with DB and current-user mocked out."""
    sess = _make_session()
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()

    async def _session():
        yield sess

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_current_user] = lambda: mock_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# /api/search
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
async def test_search_injection_not_500(client: AsyncClient, payload: str) -> None:
    r = await client.get("/api/search", params={"q": payload, "lang": "jp"})
    assert r.status_code != 500


@pytest.mark.parametrize("payload", BLANK_AFTER_STRIP_PAYLOADS)
async def test_search_null_bytes_rejected(client: AsyncClient, payload: str) -> None:
    r = await client.get("/api/search", params={"q": payload, "lang": "jp"})
    assert r.status_code == 422


@pytest.mark.parametrize("payload", SANITIZED_PAYLOADS)
async def test_search_embedded_null_bytes_sanitized(client: AsyncClient, payload: str) -> None:
    r = await client.get("/api/search", params={"q": payload, "lang": "jp"})
    assert r.status_code != 500


@pytest.mark.parametrize("payload", BLANK_PAYLOADS)
async def test_search_blank_rejected(client: AsyncClient, payload: str) -> None:
    r = await client.get("/api/search", params={"q": payload, "lang": "jp"})
    assert r.status_code == 422


async def test_search_oversized_rejected(client: AsyncClient) -> None:
    r = await client.get("/api/search", params={"q": "a" * 101, "lang": "jp"})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# /api/analyze
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
async def test_analyze_injection_not_500(
    client: AsyncClient, payload: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.routers.analyze.tokenize_japanese", lambda q: [])
    monkeypatch.setattr("app.routers.analyze.tokenize_chinese", lambda q: [])
    r = await client.post("/api/analyze", json={"query": payload, "language": "jp"})
    assert r.status_code != 500


@pytest.mark.parametrize("payload", BLANK_AFTER_STRIP_PAYLOADS)
async def test_analyze_null_bytes_rejected(client: AsyncClient, payload: str) -> None:
    r = await client.post("/api/analyze", json={"query": payload, "language": "jp"})
    assert r.status_code == 422


@pytest.mark.parametrize("payload", SANITIZED_PAYLOADS)
async def test_analyze_embedded_null_bytes_sanitized(
    client: AsyncClient, payload: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.routers.analyze.tokenize_japanese", lambda q: [])
    monkeypatch.setattr("app.routers.analyze.tokenize_chinese", lambda q: [])
    r = await client.post("/api/analyze", json={"query": payload, "language": "jp"})
    assert r.status_code != 500


@pytest.mark.parametrize("payload", BLANK_PAYLOADS)
async def test_analyze_blank_rejected(client: AsyncClient, payload: str) -> None:
    r = await client.post("/api/analyze", json={"query": payload, "language": "jp"})
    assert r.status_code == 422


async def test_analyze_oversized_rejected(client: AsyncClient) -> None:
    r = await client.post("/api/analyze", json={"query": "a" * 501, "language": "jp"})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# /api/kanji/{char}  — guards len==1 and CJK range
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
async def test_kanji_detail_injection_rejected(client: AsyncClient, payload: str) -> None:
    encoded = urllib.parse.quote(payload, safe="")
    r = await client.get(f"/api/kanji/{encoded}")
    # 400 — failed CJK validation; 404 — path with encoded slashes doesn't match route
    assert r.status_code in (400, 404, 422)


async def test_kanji_detail_ascii_char_rejected(client: AsyncClient) -> None:
    r = await client.get("/api/kanji/A")
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# /api/kanji/search
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
async def test_kanji_search_injection_not_500(client: AsyncClient, payload: str) -> None:
    r = await client.get("/api/kanji/search", params={"value": payload})
    assert r.status_code != 500


@pytest.mark.parametrize("payload", BLANK_AFTER_STRIP_PAYLOADS)
async def test_kanji_search_null_bytes_rejected(client: AsyncClient, payload: str) -> None:
    r = await client.get("/api/kanji/search", params={"value": payload})
    assert r.status_code == 422


@pytest.mark.parametrize("payload", SANITIZED_PAYLOADS)
async def test_kanji_search_embedded_null_bytes_sanitized(
    client: AsyncClient, payload: str
) -> None:
    r = await client.get("/api/kanji/search", params={"value": payload})
    assert r.status_code != 500


@pytest.mark.parametrize("payload", BLANK_PAYLOADS)
async def test_kanji_search_blank_rejected(client: AsyncClient, payload: str) -> None:
    r = await client.get("/api/kanji/search", params={"value": payload})
    assert r.status_code == 422


async def test_kanji_search_oversized_rejected(client: AsyncClient) -> None:
    r = await client.get("/api/kanji/search", params={"value": "a" * 51})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# /api/vocabulary  (auth-required)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
async def test_vocabulary_injection_not_500(
    authed_client: AsyncClient, payload: str
) -> None:
    r = await authed_client.post(
        "/api/vocabulary",
        json={"language": "jp", "expression": payload, "reading": "test", "meaning": "test"},
    )
    assert r.status_code != 500


@pytest.mark.parametrize("payload", BLANK_AFTER_STRIP_PAYLOADS)
async def test_vocabulary_null_bytes_rejected(
    authed_client: AsyncClient, payload: str
) -> None:
    r = await authed_client.post(
        "/api/vocabulary",
        json={"language": "jp", "expression": payload, "reading": "test", "meaning": "test"},
    )
    assert r.status_code == 422


async def test_vocabulary_expression_oversized_rejected(authed_client: AsyncClient) -> None:
    r = await authed_client.post(
        "/api/vocabulary",
        json={"language": "jp", "expression": "a" * 101, "reading": "r", "meaning": "m"},
    )
    assert r.status_code == 422
