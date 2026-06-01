"""Integration tests for GET /api/search."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.schemas.search import DictEntry
from app.schemas.page import Page


# ---------------------------------------------------------------------------
# Fake service responses
# ---------------------------------------------------------------------------

_JP_ENTRY = DictEntry(
    id="100",
    lang="jp",
    headword="食べる",
    reading="たべる",
    definitions=["to eat"],
    jlpt_level=5,
    is_common=True,
)

_CN_ENTRY = DictEntry(
    id="200",
    lang="cn",
    headword="你好",
    simplified="你好",
    traditional="你好",
    pinyin="nǐ hǎo",
    definitions=["hello"],
    hsk_level=1,
)

_CN_RAW = {
    "id": 200,
    "traditional": "你好",
    "simplified": "你好",
    "pinyin": "ni3 hao3",
    "definitions": ["hello"],
    "hsk_level": 1,
}

_NEKO_JP = DictEntry(
    id="300",
    lang="jp",
    headword="猫",
    reading="ねこ",
    definitions=["cat", "feline"],
    jlpt_level=5,
    is_common=True,
)

_NEKO_CN_RAW = {
    "id": 301,
    "traditional": "貓",
    "simplified": "猫",
    "pinyin": "mao1",
    "definitions": ["cat"],
    "hsk_level": 2,
}


# ---------------------------------------------------------------------------
# JP search hits jmdict
# ---------------------------------------------------------------------------


async def test_jp_search_returns_200(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _fake(q, s, *, limit, offset, **kwargs):
        return [_JP_ENTRY], 1

    monkeypatch.setattr("app.routers.search.jmdict.search_jmdict", _fake)
    r = await client.get("/api/search", params={"q": "食べる", "lang": "jp"})
    assert r.status_code == 200


async def test_jp_search_calls_jmdict(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    called = {}

    async def _fake_jmdict(q, session, *, limit, offset, **kwargs):
        called["q"] = q
        called["lang"] = "jp"
        return [_JP_ENTRY], 1

    monkeypatch.setattr("app.routers.search.jmdict.search_jmdict", _fake_jmdict)
    await client.get("/api/search", params={"q": "食べる", "lang": "jp"})
    assert called.get("lang") == "jp"


async def test_jp_search_returns_dict_entry_list(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _fake(q, s, *, limit, offset, **kwargs):
        return [_JP_ENTRY], 1

    monkeypatch.setattr("app.routers.search.jmdict.search_jmdict", _fake)
    r = await client.get("/api/search", params={"q": "食べる", "lang": "jp"})
    data = r.json()
    assert "items" in data
    items = data["items"]
    assert len(items) == 1
    assert items[0]["lang"] == "jp"
    assert items[0]["definitions"] == ["to eat"]


async def test_jp_search_page_structure(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _fake(q, s, *, limit, offset, **kwargs):
        return [_JP_ENTRY], 1

    monkeypatch.setattr("app.routers.search.jmdict.search_jmdict", _fake)
    r = await client.get("/api/search", params={"q": "食べる", "lang": "jp"})
    data = r.json()
    for key in ("total", "page", "per_page", "total_pages", "items"):
        assert key in data, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# CN search hits cedict
# ---------------------------------------------------------------------------


async def test_cn_search_returns_200(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _fake(q, lang, s, *, limit, offset, **kwargs):
        return [_CN_RAW], 1

    monkeypatch.setattr("app.routers.search.cedict.search_cedict", _fake)
    r = await client.get("/api/search", params={"q": "你好", "lang": "cn"})
    assert r.status_code == 200


async def test_cn_search_calls_cedict(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    called = {}

    async def _fake_cedict(q, lang, session, *, limit, offset, **kwargs):
        called["q"] = q
        called["lang"] = lang
        return [_CN_RAW], 1

    monkeypatch.setattr("app.routers.search.cedict.search_cedict", _fake_cedict)
    await client.get("/api/search", params={"q": "你好", "lang": "cn"})
    assert called.get("lang") == "cn"


async def test_cn_search_returns_dict_entry_list(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _fake(q, lang, s, *, limit, offset, **kwargs):
        return [_CN_RAW], 1

    monkeypatch.setattr("app.routers.search.cedict.search_cedict", _fake)
    r = await client.get("/api/search", params={"q": "你好", "lang": "cn"})
    data = r.json()
    items = data["items"]
    assert len(items) == 1
    assert items[0]["lang"] == "cn"
    assert items[0]["definitions"] == ["hello"]


async def test_cn_traditional_search(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    called = {}

    async def _fake_cedict(q, lang, session, *, limit, offset, **kwargs):
        called["lang"] = lang
        return [_CN_RAW], 1

    monkeypatch.setattr("app.routers.search.cedict.search_cedict", _fake_cedict)
    await client.get("/api/search", params={"q": "你好", "lang": "cn_traditional"})
    assert called.get("lang") == "cn_traditional"


# ---------------------------------------------------------------------------
# Validation / edge cases
# ---------------------------------------------------------------------------


async def test_search_422_blank_query(client: AsyncClient) -> None:
    r = await client.get("/api/search", params={"q": "   ", "lang": "jp"})
    assert r.status_code == 422


async def test_search_422_invalid_lang(client: AsyncClient) -> None:
    r = await client.get("/api/search", params={"q": "hello", "lang": "fr"})
    assert r.status_code == 422


async def test_search_empty_result_returns_page(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _fake(q, s, *, limit, offset, **kwargs):
        return [], 0

    monkeypatch.setattr("app.routers.search.jmdict.search_jmdict", _fake)
    r = await client.get("/api/search", params={"q": "zzz", "lang": "jp"})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0
    assert data["items"] == []


# ---------------------------------------------------------------------------
# Reverse search — JP (English → Japanese)
# ---------------------------------------------------------------------------


async def test_reverse_jp_cat_returns_neko(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _fake(normalized, s, *, limit, offset, **kwargs):
        return [_NEKO_JP], 1

    monkeypatch.setattr("app.routers.search.jmdict.search_jmdict_reverse", _fake)
    r = await client.get("/api/search", params={"q": "cat", "lang": "jp"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 1
    assert items[0]["headword"] == "猫"


async def test_reverse_jp_article_stripped(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list = []

    async def _fake(normalized, s, *, limit, offset, **kwargs):
        calls.append(normalized.text)
        return [_NEKO_JP], 1

    monkeypatch.setattr("app.routers.search.jmdict.search_jmdict_reverse", _fake)
    await client.get("/api/search", params={"q": "a cat", "lang": "jp"})
    assert calls == ["cat"]


async def test_reverse_jp_a_cat_same_result_as_cat(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _fake(normalized, s, *, limit, offset, **kwargs):
        return [_NEKO_JP], 1

    monkeypatch.setattr("app.routers.search.jmdict.search_jmdict_reverse", _fake)
    r_bare = await client.get("/api/search", params={"q": "cat", "lang": "jp"})
    r_article = await client.get("/api/search", params={"q": "a cat", "lang": "jp"})
    assert r_bare.json()["items"][0]["headword"] == r_article.json()["items"][0]["headword"]


async def test_reverse_jp_russian_uses_ru_script(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list = []

    async def _fake(normalized, s, *, limit, offset, **kwargs):
        calls.append(normalized.script)
        return [_NEKO_JP], 1

    monkeypatch.setattr("app.routers.search.jmdict.search_jmdict_reverse", _fake)
    r = await client.get("/api/search", params={"q": "кошка", "lang": "jp"})
    assert r.status_code == 200
    assert calls == ["ru"]


async def test_reverse_jp_russian_returns_entry(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _fake(normalized, s, *, limit, offset, **kwargs):
        return [_NEKO_JP], 1

    monkeypatch.setattr("app.routers.search.jmdict.search_jmdict_reverse", _fake)
    r = await client.get("/api/search", params={"q": "кошка", "lang": "jp"})
    items = r.json()["items"]
    assert len(items) >= 1
    assert items[0]["headword"] == "猫"


# ---------------------------------------------------------------------------
# Reverse search — CN (English → Chinese)
# ---------------------------------------------------------------------------


async def test_reverse_cn_cat_calls_cedict_reverse(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    called = {}

    async def _fake(normalized, lang, s, *, limit, offset, **kwargs):
        called["text"] = normalized.text
        called["lang"] = lang
        return [_NEKO_CN_RAW], 1

    monkeypatch.setattr("app.routers.search.cedict.search_cedict_reverse", _fake)
    r = await client.get("/api/search", params={"q": "cat", "lang": "cn"})
    assert r.status_code == 200
    assert called["text"] == "cat"
    assert called["lang"] == "cn"


async def test_reverse_cn_cat_returns_neko(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _fake(normalized, lang, s, *, limit, offset, **kwargs):
        return [_NEKO_CN_RAW], 1

    monkeypatch.setattr("app.routers.search.cedict.search_cedict_reverse", _fake)
    r = await client.get("/api/search", params={"q": "cat", "lang": "cn"})
    items = r.json()["items"]
    assert len(items) >= 1
    assert items[0]["headword"] == "猫"


async def test_reverse_cn_traditional_routes_to_reverse(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    called = {}

    async def _fake(normalized, lang, s, *, limit, offset, **kwargs):
        called["lang"] = lang
        return [_NEKO_CN_RAW], 1

    monkeypatch.setattr("app.routers.search.cedict.search_cedict_reverse", _fake)
    await client.get("/api/search", params={"q": "cat", "lang": "cn_traditional"})
    assert called.get("lang") == "cn_traditional"


# ---------------------------------------------------------------------------
# Forward paths are unaffected by reverse routing
# ---------------------------------------------------------------------------


async def test_forward_jp_cjk_query_does_not_use_reverse(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    reverse_called = {}

    async def _fake_reverse(normalized, s, *, limit, offset, **kwargs):
        reverse_called["hit"] = True
        return [], 0

    async def _fake_forward(q, s, *, limit, offset, **kwargs):
        return [_JP_ENTRY], 1

    monkeypatch.setattr("app.routers.search.jmdict.search_jmdict_reverse", _fake_reverse)
    monkeypatch.setattr("app.routers.search.jmdict.search_jmdict", _fake_forward)
    r = await client.get("/api/search", params={"q": "食べる", "lang": "jp"})
    assert r.status_code == 200
    assert "hit" not in reverse_called
