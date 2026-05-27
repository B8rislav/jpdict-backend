"""Integration tests for GET /api/kanji/{char}."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from app.schemas.kanji import KanjiCard
from app.services import cache as cache_svc

_FAKE_CARD = KanjiCard(
    character="水",
    stroke_count=4,
    radicals=["水"],
    on_readings=["スイ"],
    kun_readings=["みず"],
    meanings=["water"],
    jlpt_level="N5",
)


# ---------------------------------------------------------------------------
# 400 — non-single or non-CJK input
# ---------------------------------------------------------------------------


async def test_multi_char_returns_400(client: AsyncClient) -> None:
    r = await client.get("/api/kanji/水火")
    assert r.status_code == 400


async def test_ascii_char_returns_400(client: AsyncClient) -> None:
    r = await client.get("/api/kanji/A")
    assert r.status_code == 400


async def test_latin_word_returns_400(client: AsyncClient) -> None:
    r = await client.get("/api/kanji/ab")
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# 404 — unknown kanji (not in DB, not in cache)
# ---------------------------------------------------------------------------


async def test_unknown_char_returns_404(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cache_svc, "get_kanji_cached", AsyncMock(return_value=None))
    monkeypatch.setattr("app.routers.kanji.jmdict.get_kanji_detail", AsyncMock(return_value=None))

    r = await client.get("/api/kanji/㐀")  # rare extension-A character
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# 200 — cache miss: DB is queried
# ---------------------------------------------------------------------------


async def test_cache_miss_queries_db(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    get_cached = AsyncMock(return_value=None)
    get_detail = AsyncMock(return_value=_FAKE_CARD)
    set_cache = AsyncMock()

    monkeypatch.setattr(cache_svc, "get_kanji_cached", get_cached)
    monkeypatch.setattr("app.routers.kanji.jmdict.get_kanji_detail", get_detail)
    monkeypatch.setattr(cache_svc, "set_kanji_cache", set_cache)

    r = await client.get("/api/kanji/水")
    assert r.status_code == 200
    get_detail.assert_called_once()


async def test_cache_miss_writes_to_cache(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_cache = AsyncMock()
    monkeypatch.setattr(cache_svc, "get_kanji_cached", AsyncMock(return_value=None))
    monkeypatch.setattr("app.routers.kanji.jmdict.get_kanji_detail", AsyncMock(return_value=_FAKE_CARD))
    monkeypatch.setattr(cache_svc, "set_kanji_cache", set_cache)

    await client.get("/api/kanji/水")
    set_cache.assert_called_once()


# ---------------------------------------------------------------------------
# 200 — cache hit: DB is NOT queried
# ---------------------------------------------------------------------------


async def test_cache_hit_skips_db(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    get_cached = AsyncMock(return_value=_FAKE_CARD)
    get_detail = AsyncMock(return_value=_FAKE_CARD)

    monkeypatch.setattr(cache_svc, "get_kanji_cached", get_cached)
    monkeypatch.setattr("app.routers.kanji.jmdict.get_kanji_detail", get_detail)

    r = await client.get("/api/kanji/水")
    assert r.status_code == 200
    get_detail.assert_not_called()


async def test_cache_hit_returns_cached_data(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cache_svc, "get_kanji_cached", AsyncMock(return_value=_FAKE_CARD))

    r = await client.get("/api/kanji/水")
    assert r.status_code == 200
    data = r.json()
    assert data["character"] == "水"
    assert data["jlpt_level"] == "N5"


# ---------------------------------------------------------------------------
# 200 — response shape
# ---------------------------------------------------------------------------


async def test_kanji_response_shape(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cache_svc, "get_kanji_cached", AsyncMock(return_value=_FAKE_CARD))

    r = await client.get("/api/kanji/水")
    data = r.json()
    for field in ("character", "stroke_count", "radicals", "on_readings", "kun_readings", "meanings", "jlpt_level"):
        assert field in data, f"Missing field: {field}"
    assert isinstance(data["on_readings"], list)
    assert isinstance(data["kun_readings"], list)
    assert isinstance(data["meanings"], list)


async def test_kanji_meanings_are_strings(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cache_svc, "get_kanji_cached", AsyncMock(return_value=_FAKE_CARD))
    r = await client.get("/api/kanji/水")
    for m in r.json()["meanings"]:
        assert isinstance(m, str)
