"""Integration tests for POST /api/analyze."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers — fake tokenizer outputs
# ---------------------------------------------------------------------------

def _leveled_jp_tokens(n: int) -> list[dict]:
    """Return n Japanese tokens all with a known JLPT level."""
    return [
        {
            "surface": "私",
            "dictionary_form": "私",
            "reading": "ワタシ",
            "pos": "代名詞",
            "jlpt_level": 5,
            "hsk_level": None,
            "pinyin": None,
        }
    ] * n


def _unleveled_jp_tokens(n: int) -> list[dict]:
    """Return n Japanese tokens with no JLPT level (unknown)."""
    return [
        {
            "surface": "懸念",
            "dictionary_form": "懸念",
            "reading": "ケネン",
            "pos": "名詞",
            "jlpt_level": None,
            "hsk_level": None,
            "pinyin": None,
        }
    ] * n


def _leveled_cn_tokens(n: int) -> list[dict]:
    """Return n Chinese tokens all with a known HSK level."""
    return [
        {
            "surface": "你",
            "dictionary_form": "你",
            "reading": None,
            "pos": "r",
            "jlpt_level": None,
            "hsk_level": 1,
            "pinyin": "nǐ",
        }
    ] * n


# ---------------------------------------------------------------------------
# 200 — full breakdown present (≥ 3 leveled tokens)
# ---------------------------------------------------------------------------


async def test_analyze_jp_200_with_breakdown(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.routers.analyze.tokenize_japanese", lambda q: _leveled_jp_tokens(3))
    r = await client.post("/api/analyze", json={"query": "私は私は私", "language": "jp"})
    assert r.status_code == 200
    data = r.json()
    assert data["level_breakdown"] is not None
    assert data["level_breakdown"]["leveled_count"] >= 3


async def test_analyze_cn_200_with_breakdown(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.routers.analyze.tokenize_chinese", lambda q: _leveled_cn_tokens(3))
    r = await client.post("/api/analyze", json={"query": "你你你", "language": "cn"})
    assert r.status_code == 200
    assert r.json()["level_breakdown"] is not None


# ---------------------------------------------------------------------------
# 206 — partial content (fewer than 3 leveled tokens)
# ---------------------------------------------------------------------------


async def test_analyze_jp_206_without_breakdown(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.routers.analyze.tokenize_japanese", lambda q: _unleveled_jp_tokens(5))
    r = await client.post("/api/analyze", json={"query": "懸念懸念懸念", "language": "jp"})
    assert r.status_code == 206
    assert r.json()["level_breakdown"] is None


async def test_analyze_jp_206_two_leveled_tokens(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 2 leveled < threshold of 3 → 206
    monkeypatch.setattr("app.routers.analyze.tokenize_japanese", lambda q: _leveled_jp_tokens(2))
    r = await client.post("/api/analyze", json={"query": "私は私", "language": "jp"})
    assert r.status_code == 206


async def test_analyze_cn_206_without_breakdown(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.routers.analyze.tokenize_chinese", lambda q: _unleveled_jp_tokens(4))
    r = await client.post("/api/analyze", json={"query": "你好", "language": "cn"})
    assert r.status_code == 206


# ---------------------------------------------------------------------------
# 400 — classify raises ValueError (empty-after-strip / always-empty path)
# ---------------------------------------------------------------------------


async def test_analyze_400_classify_raises(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _raise(q: str, lang: str):
        raise ValueError("forced")

    monkeypatch.setattr("app.routers.analyze.classify", _raise)
    monkeypatch.setattr("app.routers.analyze.tokenize_japanese", lambda q: [])
    r = await client.post("/api/analyze", json={"query": "valid query", "language": "jp"})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# 422 — schema validation failures
# ---------------------------------------------------------------------------


async def test_analyze_422_blank_query(client: AsyncClient) -> None:
    r = await client.post("/api/analyze", json={"query": "   ", "language": "jp"})
    assert r.status_code == 422


async def test_analyze_422_missing_language(client: AsyncClient) -> None:
    r = await client.post("/api/analyze", json={"query": "hello"})
    assert r.status_code == 422


async def test_analyze_422_invalid_language(client: AsyncClient) -> None:
    r = await client.post("/api/analyze", json={"query": "hello", "language": "fr"})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Response structure
# ---------------------------------------------------------------------------


async def test_analyze_response_fields(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.routers.analyze.tokenize_japanese", lambda q: _leveled_jp_tokens(3))
    r = await client.post("/api/analyze", json={"query": "私は私は私", "language": "jp"})
    data = r.json()
    assert "query" in data
    assert "language" in data
    assert "query_type" in data
    assert "tokens" in data
    assert isinstance(data["tokens"], list)


async def test_analyze_tokens_have_correct_shape(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.routers.analyze.tokenize_japanese", lambda q: _leveled_jp_tokens(1))
    r = await client.post("/api/analyze", json={"query": "私", "language": "jp"})
    assert r.status_code in (200, 206)
    token = r.json()["tokens"][0]
    assert "surface" in token
    assert "pos" in token
