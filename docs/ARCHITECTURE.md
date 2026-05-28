# Architecture

High-level overview of how the JpDict backend is structured and how a request flows through it.

## Component diagram

```
                           HTTP Request
                                │
               ┌────────────────▼─────────────────┐
               │  CORS + SecurityHeadersMiddleware  │  app/main.py
               └────────────────┬─────────────────┘
                                │
               ┌────────────────▼─────────────────┐
               │           Rate Limiter            │  app/core/rate_limit.py
               │    Redis key: rl:ip:{ip}          │◄──── Redis 7
               │    or rl:user:{user_id}           │
               └────────────────┬─────────────────┘
                                │
         ┌──────────────────────┼──────────────────────┐
         │                      │                      │
┌────────▼────────┐  ┌──────────▼──────────┐  ┌───────▼──────────┐
│  /api/auth/*    │  │  /api/analyze        │  │  /api/vocabulary  │
│  /api/search    │  │  /api/kanji/*        │  │  /api/history     │
│  /api/reibun/*  │  │  (rate-limited)      │  │  (auth required)  │
│  (public)       │  └──────────┬──────────┘  └───────┬──────────┘
└────────┬────────┘             │                      │
         │              ┌───────▼──────────┐  ┌───────▼──────────┐
┌────────▼────────┐     │   NLP Pipeline   │  │  get_current_user │
│ security.py     │     │  classifier.py   │  │  deps.py          │
│ JWT + bcrypt    │     │  japanese.py     │  │  (JWT → User ORM) │
└─────────────────┘     │  chinese.py      │  └───────┬──────────┘
                        └───────┬──────────┘          │
                                │                      │
                        ┌───────▼──────────────────────▼──────────┐
                        │               Services                   │
                        │  jmdict.py  cedict.py  reibun.py         │
                        │  cache.py  (two-level kanji cache)       │
                        └───────┬──────────────────────────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
  ┌───────────▼───────┐  ┌──────▼───────┐  ┌─────▼───────────┐
  │  TTLCache          │  │ kanji_cache  │  │  SQLAlchemy     │
  │  (in-memory)       │  │ table (JSONB)│  │  AsyncSession   │
  │  512 kanji slots   │  │ 30-day TTL   │  └─────┬───────────┘
  └────────────────────┘  └──────────────┘        │
                                          ┌────────▼────────────┐
                                          │    PostgreSQL 15     │
                                          │  jmdict_entries      │
                                          │  kanjidic_entries    │
                                          │  cedict_entries      │
                                          │  reibun_entries      │
                                          │  users               │
                                          │  saved_words         │
                                          │  search_history      │
                                          │  kanji_cache         │
                                          └─────────────────────┘
```

## Request lifecycle

1. **CORS + security headers** — `CORSMiddleware` checks the `Origin` header against `ALLOWED_ORIGINS`; `SecurityHeadersMiddleware` appends `X-Content-Type-Options`, `X-Frame-Options`, and `Referrer-Policy` to every response.

2. **Rate limiter** — `Depends(rate_limit)` on each public router. Reads an optional Bearer token: if valid, keys by `rl:user:{user_id}` at 120 req/min; otherwise keys by `rl:ip:{client_ip}` at 60 req/min. Returns 429 with `Retry-After: 60` on breach. Fails open if Redis is unreachable.

3. **Router** — FastAPI dispatches to the matching path function in `app/routers/`.

4. **Auth (guarded routes)** — `Depends(get_current_user)` in `app/core/deps.py` extracts the Bearer token, decodes the JWT, enforces `type == "access"`, and returns the `User` ORM object or raises 401.

5. **NLP pipeline** — `POST /api/analyze` calls `classify()` to detect query type by Unicode ranges, then `tokenize_japanese()` (SudachiPy mode C) or `tokenize_chinese()` (jieba + pypinyin) to segment text and attach JLPT/HSK levels.

6. **Services + cache** — Dictionary lookups go through `app/services/jmdict.py` or `cedict.py`. Kanji detail cards (`GET /api/kanji/{char}`) check the in-memory `TTLCache` first, then the `kanji_cache` Postgres table, then fall back to a live KANJIDIC/JMdict query. Reibun results are cached similarly per `(expression, page, per_page)`.

7. **SQLAlchemy async session** — `get_session()` yields an `AsyncSession` bound to `AsyncEngine`; every session is auto-closed after the request via `async with`.

## Where specific concerns live

| Concern | Location |
|---|---|
| In-memory cache (kanji, reibun) | `app/services/cache.py` — `TTLCache(maxsize=512/1024, ttl=600)` |
| Postgres cache | `app/services/cache.py` + `kanji_cache` table (migration 0001) |
| NLP pipeline entry point | `app/routers/analyze.py:46` → `app/services/nlp/` |
| JWT auth | `app/core/security.py` + `app/core/deps.py:get_current_user` |
| Security headers middleware | `app/main.py:16–22` |
| Rate limiter | `app/core/rate_limit.py` |
| SSE explain endpoint | **Not yet implemented** — planned in `app/routers/explain.py` (see TASKS.md §8) |

## Key design choices

- **JSONB for glosses** — `senses`/`definitions` are stored as JSONB so the same column holds `{en: [...], ru: [...]}` without schema migrations per language.
- **GIN trigram indexes** — `pg_trgm` GIN indexes on `jmdict_entries.kanji_forms`, `cedict_entries.simplified`, `reibun_entries.sentence_jp`, and `saved_words.expression` support prefix and similarity search without full-text search complexity.
- **Array columns** — `kanji_forms[]` and `reading_forms[]` use PostgreSQL arrays so lookups use the `ANY` operator rather than a join table.
- **Fail-open rate limiter** — if Redis is unavailable the limiter returns without raising, keeping the API available under degraded conditions.
- **Two-level kanji cache** — TTLCache handles hot kanji (猫, 人) in microseconds; the Postgres `kanji_cache` table survives process restarts and works across multiple Docker workers.
