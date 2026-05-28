# API Reference

Every public endpoint in the JpDict backend. `Auth` column: **No** = unauthenticated; **Bearer** = `Authorization: Bearer <access_token>`; **Cookie** = `refresh_token` httpOnly cookie.

Rate limit applies to endpoints that include `Depends(rate_limit)` on the router: 60 req/min per IP (anonymous) or 120 req/min per user (authenticated with a valid token).

## Auth

| Method | Path | Auth | Rate limit | Request schema | Response schema | Source |
|---|---|---|---|---|---|---|
| POST | `/api/auth/register` | No | No | `UserCreate` | `UserResponse` 201 / 409 | [auth.py:23](../app/routers/auth.py#L23) |
| POST | `/api/auth/login` | No | No | `UserCreate` | `TokenResponse` + `Set-Cookie: refresh_token` | [auth.py:40](../app/routers/auth.py#L40) |
| POST | `/api/auth/refresh` | Cookie | No | — | `TokenResponse` | [auth.py:58](../app/routers/auth.py#L58) |

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
| GET | `/api/search` | No | Yes | query params | `Page[DictEntry]` | [search.py:17](../app/routers/search.py#L17) |
| GET | `/api/kanji/search` | No | Yes | query params | `{ result_count, kanjis[] }` | [kanji.py:26](../app/routers/kanji.py#L26) |
| GET | `/api/kanji/{char}` | No | Yes | path param | `KanjiCard` 200 / 404 | [kanji.py:84](../app/routers/kanji.py#L84) |
| GET | `/api/reibun/search/{word_id}` | No | Yes | path + query | `ReibunSearchResponse` | [reibun.py:12](../app/routers/reibun.py#L12) |

**`GET /api/search` query params** — `q` (1–100 chars), `lang` (`jp` | `cn` | `cn_traditional`), `pg` (default 1), `per_page` (default 20, max 100)  
**`Page[DictEntry]`** — `{ items: DictEntry[], total, page, per_page, pages }`  
**`DictEntry`** — `{ id, lang, headword, reading, traditional?, simplified?, pinyin?, definitions: {en[], ru[]}, jlpt_level?, hsk_level? }`

**`GET /api/kanji/search` query params** — `value` (1–50 chars); CJK character, kana reading, or English prefix  
**`GET /api/kanji/search` response** — `{ result_count: int, kanjis: [{id, kanji, definition}] }` (max 20 results)

**`KanjiCard`** — `{ character, stroke_count, radicals[], on_readings[], kun_readings[], meanings[], meanings_ru[], jlpt_level? }`

**`GET /api/reibun/search/{word_id}` query params** — `pg` (default 1), `perPage` (default 10, max 100)  
**`ReibunSearchResponse`** — `{ result_count, pg, perPage, reibuns: [{sentence_jp, reading_jp?, translation_ru?, translation_en?, source}] }`

## Vocabulary

| Method | Path | Auth | Rate limit | Request schema | Response schema | Source |
|---|---|---|---|---|---|---|
| GET | `/api/vocabulary` | Bearer | No | — | `SavedWord[]` | [vocabulary.py:17](../app/routers/vocabulary.py#L17) |
| POST | `/api/vocabulary` | Bearer | No | `SavedWordCreate` | `SavedWord` 201 / 409 | [vocabulary.py:28](../app/routers/vocabulary.py#L28) |
| PATCH | `/api/vocabulary/{word_id}` | Bearer | No | `SavedWordStatusUpdate` | `SavedWord` 200 / 403 / 404 | [vocabulary.py:54](../app/routers/vocabulary.py#L54) |
| DELETE | `/api/vocabulary/{word_id}` | Bearer | No | — | 204 / 403 / 404 | [vocabulary.py:75](../app/routers/vocabulary.py#L75) |

**`SavedWordCreate`** — `{ language, expression, reading, meaning, jlpt_level?, hsk_level?, status: "new"|"learning"|"known" }`  
**`SavedWordStatusUpdate`** — `{ status: "new"|"learning"|"known" }`  
**`SavedWord`** — `{ id, user_id, language, expression, reading, meaning, jlpt_level?, hsk_level?, status, added_at }`

409 Conflict is returned when `(user_id, language, expression)` already exists.

## History

| Method | Path | Auth | Rate limit | Request schema | Response schema | Source |
|---|---|---|---|---|---|---|
| POST | `/api/history` | Bearer | No | `HistoryCreate` | `HistoryEntry` 201 | [history.py:34](../app/routers/history.py#L34) |
| GET | `/api/history` | Bearer | No | query params | `HistoryEntry[]` | [history.py:52](../app/routers/history.py#L52) |
| DELETE | `/api/history/{entry_id}` | Bearer | No | — | 204 (noop if not found) | [history.py:67](../app/routers/history.py#L67) |
| DELETE | `/api/history` | Bearer | No | — | 204 | [history.py:79](../app/routers/history.py#L79) |

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
