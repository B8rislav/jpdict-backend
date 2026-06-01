# API Reference

> **The canonical API contract is the live OpenAPI schema at `GET /openapi.json`** (browsable at `/docs`). The frontend generates its types from it, so it is always authoritative. This document is the prose companion — read it for intent and shapes, but defer to the live schema when they disagree.

Every public endpoint in the JpDict backend. `Auth` column: **No** = unauthenticated; **Bearer** = `Authorization: Bearer <access_token>`; **Cookie** = `refresh_token` httpOnly cookie.

Rate limit applies to endpoints that include `Depends(rate_limit)` on the router: 60 req/min per IP (anonymous) or 120 req/min per user (authenticated with a valid token).

## Auth

| Method | Path | Auth | Rate limit | Request schema | Response schema | Source |
|---|---|---|---|---|---|---|
| POST | `/api/auth/register` | No | No | `UserCreate` | `UserResponse` 201 / 409 | [auth.py:23](../app/routers/auth.py#L23) |
| POST | `/api/auth/login` | No | No | `UserCreate` | `TokenResponse` + `Set-Cookie: refresh_token` | [auth.py:41](../app/routers/auth.py#L41) |
| POST | `/api/auth/refresh` | Cookie | No | — | `TokenResponse` | [auth.py:60](../app/routers/auth.py#L60) |

**`UserCreate`** — `{ email: str, password: str, language: "jp" | "cn" }`  
**`UserResponse`** — `{ id: UUID, email: str, language: str, created_at: datetime }`  
**`TokenResponse`** — `{ access_token: str, token_type: "bearer" }`

## Analysis

| Method | Path | Auth | Rate limit | Request schema | Response schema | Source |
|---|---|---|---|---|---|---|
| POST | `/api/analyze` | No | Yes | `AnalyzeRequest` | `AnalyzeResponse` 200 / 206 | [analyze.py:46](../app/routers/analyze.py#L46) |

**`AnalyzeRequest`** — `{ query: str, language: "jp" | "cn" }`  
**`AnalyzeResponse`** — `{ query, language, query_type, tokens: TokenResult[], level_breakdown: LevelBreakdown | null }`  
**`TokenResult`** — `{ surface, dictionary_form, reading, pos, jlpt_level, hsk_level, pinyin }`  
**`LevelBreakdown`** — `{ distribution: {N5..N1 | HSK1..6 | unknown: int}, leveled_count, total_count }`

Returns 206 when fewer than 3 tokens have a known JLPT/HSK level (breakdown is `null`).

## Dictionary search

| Method | Path | Auth | Rate limit | Request schema | Response schema | Source |
|---|---|---|---|---|---|---|
| GET | `/api/search` | No | Yes | query params | `Page[DictEntry]` | [search.py:19](../app/routers/search.py#L19) |
| GET | `/api/kanji/search` | No | Yes | query params | `{ result_count, kanjis[] }` | [kanji.py:27](../app/routers/kanji.py#L27) |
| GET | `/api/kanji/{char}` | No | Yes | path param | `KanjiCard` 200 / 404 | [kanji.py:94](../app/routers/kanji.py#L94) |
| GET | `/api/hanzi/{char}` | No | Yes | path param | `HanziCard` 200 / 404 | [kanji.py:134](../app/routers/kanji.py#L134) |
| GET | `/api/reibun/search/{word_id}` | No | Yes | path + query | `ReibunSearchResponse` | [reibun.py:12](../app/routers/reibun.py#L12) |

**`GET /api/search` query params** — `q` (1–100 chars), `lang` (`jp` | `cn` | `cn_traditional`), `pg` (default 1), `per_page` (default 20, max 100)  
**`Page[DictEntry]`** — `{ items: DictEntry[], total, page, per_page, pages }`  
**`DictEntry`** — `{ id, lang, headword, reading, traditional?, simplified?, pinyin?, definitions: {en[], ru[]}, jlpt_level?, hsk_level? }`

**`GET /api/kanji/search` query params** — `value` (1–50 chars); CJK character, kana reading, or English prefix  
**`GET /api/kanji/search` response** — `{ result_count: int, kanjis: [{id, kanji, definition}] }` (max 20 results)

**`KanjiCard`** — `{ character, stroke_count, radicals[], on_readings[], kun_readings[], meanings[], meanings_ru[], jlpt_level? }`

**`GET /api/hanzi/{char}`** — single Chinese character lookup from CC-CEDICT; `def_lang` (`ru` | `en`, default `ru`)
**`HanziCard`** — `{ character, pinyin, meanings[], hsk_level?, traditional? }`

**`GET /api/reibun/search/{word_id}` query params** — `pg` (default 1), `perPage` (default 10, max 100)  
**`ReibunSearchResponse`** — `{ result_count, pg, perPage, reibuns: [{sentence_jp, reading_jp?, translation_ru?, translation_en?, source}] }`

## Vocabulary

| Method | Path | Auth | Rate limit | Request schema | Response schema | Source |
|---|---|---|---|---|---|---|
| GET | `/api/vocabulary` | Bearer | No | — | `SavedWord[]` | [vocabulary.py:17](../app/routers/vocabulary.py#L17) |
| POST | `/api/vocabulary` | Bearer | No | `SavedWordCreate` | `SavedWord` 201 / 409 | [vocabulary.py:29](../app/routers/vocabulary.py#L29) |
| PATCH | `/api/vocabulary/{word_id}` | Bearer | No | `SavedWordStatusUpdate` | `SavedWord` 200 / 403 / 404 | [vocabulary.py:56](../app/routers/vocabulary.py#L56) |
| DELETE | `/api/vocabulary/{word_id}` | Bearer | No | — | 204 / 403 / 404 | [vocabulary.py:76](../app/routers/vocabulary.py#L76) |

**`SavedWordCreate`** — `{ language, expression, reading, meaning, jlpt_level?, hsk_level?, status: "new"|"learning"|"known" }`  
**`SavedWordStatusUpdate`** — `{ status: "new"|"learning"|"known" }`  
**`SavedWord`** — `{ id, user_id, language, expression, reading, meaning, jlpt_level?, hsk_level?, status, added_at }`

409 Conflict is returned when `(user_id, language, expression)` already exists.

## History

| Method | Path | Auth | Rate limit | Request schema | Response schema | Source |
|---|---|---|---|---|---|---|
| POST | `/api/history` | Bearer | No | `HistoryCreate` | `HistoryEntry` 201 | [history.py:34](../app/routers/history.py#L34) |
| GET | `/api/history` | Bearer | No | query params | `HistoryEntry[]` | [history.py:53](../app/routers/history.py#L53) |
| DELETE | `/api/history/{entry_id}` | Bearer | No | — | 204 (noop if not found) | [history.py:69](../app/routers/history.py#L69) |
| DELETE | `/api/history` | Bearer | No | — | 204 | [history.py:82](../app/routers/history.py#L82) |

**`HistoryCreate`** — `{ language, query: str (max 500), query_type: str (max 50) }`  
**`HistoryEntry`** — `{ id, language, query, query_type, searched_at }`  
**`GET /api/history` query params** — `lang` (optional), `limit` (default 50, max 200)

## Health

| Method | Path | Auth | Rate limit | Response |
|---|---|---|---|---|
| GET | `/health` | No | No | `{ status: "ok" }` |

## Planned / not yet implemented

| Method | Path | Status |
|---|---|---|
| POST | `/api/explain` | **Not implemented** — SSE stream to OpenRouter (see TASKS.md §8) |
