# Backend Tasks

> Standalone backend repo — no monorepo. Frontend lives in a separate repository.
> Docker Compose here runs only backend services: `db`, `cache`, `backend`.

---

## Phase 1 — Project Skeleton & Environment

- [x] **1.1** Init repo, add `.gitignore` (Python, `.env`, `__pycache__`, `*.pyc`)
- [x] **1.2** Create `pyproject.toml` with all pinned dependencies (fastapi, uvicorn, sqlalchemy, asyncpg, alembic, pydantic-settings, python-jose, passlib, httpx, cachetools, redis, sudachipy, hanlp, pypinyin, pytest, pytest-asyncio)
- [x] **1.3** Write `app/main.py` — FastAPI instance, lifespan context manager, `GET /health` returning `{"status": "ok"}`
- [x] **1.4** Write `app/core/config.py` — `Settings` class via `pydantic-settings` loading `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `OPENROUTER_API_KEY` from environment
- [x] **1.5** Write `docker-compose.yml` with 3 services: `db` (postgres:15-alpine:5432), `cache` (redis:7-alpine:6379), `backend` (:8000)
- [x] **1.6** Write `Dockerfile` (multi-stage: builder → runtime)
- [x] **1.7** Write `.env.example` documenting all required environment variables
- [x] **1.8** Verify: `docker compose up` starts all 3 services; `GET /health` returns 200

---

## Phase 2 — Database Schema & ORM Models

- [x] **2.1** Write `app/db/database.py` — async engine with `asyncpg`, `AsyncSession` factory via `async_sessionmaker`
- [x] **2.2** Write `app/models/user.py` — `User` model: `id` UUID PK, `email` unique, `hashed_password`, `language` enum (`jp`/`cn`), `created_at`
- [x] **2.3** Write `app/models/saved_word.py` — `SavedWord` model with `language_enum`, `word_status` enum, JLPT/HSK level columns, unique constraint `(user_id, language, expression)`
- [x] **2.4** Write `app/models/search_history.py` — `SearchHistory` model: `id`, `user_id` FK, `language`, `query`, `query_type`, `searched_at`
- [x] **2.5** Write `app/models/kanji_cache.py` — `KanjiCache` model: `id`, `character` unique, `data` JSONB, `cached_at`, `expires_at`
- [x] **2.6** Init Alembic (`alembic init alembic`), configure `env.py` for async engine
- [x] **2.7** Write initial migration enabling extensions: `pgcrypto`, `pg_trgm`; create all tables with indexes (`idx_saved_words_user_lang`, `idx_saved_words_expression_trgm` using GIN)
- [x] **2.8** Verify: `alembic upgrade head` applies cleanly; all tables and indexes exist

---

## Phase 3 — Authentication

- [ ] **3.1** Write `app/core/security.py`: `hash_password`, `verify_password` (bcrypt cost 12), `create_access_token` (15 min), `create_refresh_token` (7 days), `decode_token`
- [ ] **3.2** Write Pydantic schemas in `app/schemas/auth.py`: `UserCreate`, `UserResponse`, `TokenResponse`
- [ ] **3.3** Write `app/routers/auth.py` — `POST /api/auth/register` (201/409), `POST /api/auth/login` (200 + httpOnly refresh cookie), `POST /api/auth/refresh` (200/401)
- [ ] **3.4** Write `get_current_user` FastAPI dependency — validates Bearer token, returns `User` ORM object; used on all protected routes
- [ ] **3.5** Register auth router in `main.py`
- [ ] **3.6** Verify: register → login → call protected endpoint → refresh flow works end-to-end

---

## Phase 4 — NLP Module

- [ ] **4.1** Write `app/services/nlp/classifier.py` — `QueryType` enum (KANJI/HANZI/SENTENCE/REVERSE), Unicode range constants, `classify(query, language)` function
- [ ] **4.2** Write `app/services/nlp/japanese.py` — init SudachiPy tokenizer (mode C, SudachiDict-core), `tokenize_japanese(text) -> list[TokenResult]` with surface, dictionary form, reading (katakana), POS, JLPT level
- [ ] **4.3** Write `app/services/nlp/chinese.py` — HanLP singleton (lazy init), `tokenize_chinese(text) -> list[TokenResult]` with word segmentation, POS, pinyin (pypinyin), HSK level; support simplified + traditional
- [ ] **4.4** Write `compute_complexity(tokens)` — median JLPT/HSK level, requires ≥ 3 tokens with non-null levels, returns `int | None`
- [ ] **4.5** Write Pydantic schemas in `app/schemas/analyze.py`: `AnalyzeRequest`, `TokenResult`, `AnalyzeResponse`
- [ ] **4.6** Write `app/routers/analyze.py` — `POST /api/analyze`: 200 (full result), 206 (complexity not computable), 400 (empty/invalid query)
- [ ] **4.7** Register analyze router in `main.py`
- [ ] **4.8** Verify: `POST /api/analyze {"query":"日本語","language":"jp"}` returns tokens with readings, POS, JLPT levels, and complexity score

---

## Phase 5 — Dictionary Research & DB Integration

> Goal: replace all external dictionary API calls with data loaded into PostgreSQL at startup.
> No runtime HTTP calls to Jisho or CC-CEDICT file parsing — everything served from DB.

### 5a — Japanese dictionary (JMdict replacement for Jisho)

- [ ] **5.1** Research open Japanese dictionary sources — evaluate JMdict/JMnedict (XML, public domain), KANJIDIC2 (kanji details), Tatoeba (example sentences); choose primary source
- [ ] **5.2** Write `scripts/import_jmdict.py` — download latest `JMdict_e.gz` from `ftp.edrdg.org`, parse XML with `lxml`, extract entries: `kanji_forms`, `reading_forms`, `senses` (English glosses), `pos` tags, JLPT level from `<misc>` field
- [ ] **5.3** Add Alembic migration for `jmdict_entries` table:
  ```sql
  CREATE TABLE jmdict_entries (
      id SERIAL PRIMARY KEY,
      kanji_forms TEXT[],
      reading_forms TEXT[],
      senses JSONB NOT NULL,
      jlpt_level SMALLINT,
      common BOOLEAN DEFAULT FALSE
  );
  CREATE INDEX idx_jmdict_kanji_gin ON jmdict_entries USING GIN (kanji_forms);
  CREATE INDEX idx_jmdict_reading_gin ON jmdict_entries USING GIN (reading_forms);
  ```
- [ ] **5.4** Write `scripts/import_kanjidic2.py` — download `kanjidic2.xml.gz`, parse entries: character, stroke count, radicals, `on_readings`, `kun_readings`, JLPT level, meanings (English); load into `kanjidic_entries` table
- [ ] **5.5** Add Alembic migration for `kanjidic_entries` table: `character` (unique), `stroke_count`, `radicals` TEXT[], `on_readings` TEXT[], `kun_readings` TEXT[], `meanings` TEXT[], `jlpt_level`
- [ ] **5.6** Write `app/services/jmdict.py` — `search_jmdict(query, mode) -> list[DictEntry]` querying `jmdict_entries` via GIN index; `get_kanji_detail(char) -> KanjiCard` from `kanjidic_entries`
- [ ] **5.7** Add one-shot `make import-jp` target (or `docker compose run backend python scripts/import_jmdict.py`) to populate tables; add to `entrypoint.sh` as idempotent seed step

### 5b — Chinese dictionary (CC-CEDICT into DB)

- [ ] **5.8** Research open Chinese dictionary sources — evaluate CC-CEDICT (simplified+traditional, pinyin, English), MakeMeAHanzi (stroke data), HSK wordlists; choose primary source
- [ ] **5.9** Write `scripts/import_cedict.py` — download latest `cedict_ts.u8`, parse line-by-line regex, extract `traditional`, `simplified`, `pinyin`, `definitions`; bulk-insert into `cedict_entries` table
- [ ] **5.10** Add Alembic migration for `cedict_entries` table: `id`, `traditional`, `simplified`, `pinyin`, `definitions` TEXT[], `hsk_level`; GIN index on `simplified` and `traditional`
- [ ] **5.11** Write `app/services/cedict.py` — `search_cedict(query, lang) -> list[DictEntry]` — DB lookup supporting both simplified and traditional input; `lang` param selects which column to match
- [ ] **5.12** Add HSK level data: find open HSK 1-6 wordlist (e.g. GitHub `andrewbaxter/hsk`), write `scripts/import_hsk.py` to update `hsk_level` on matching `cedict_entries` rows

### 5c — Wire into routers

- [ ] **5.13** Write `app/schemas/search.py` — `DictEntry` schema
- [ ] **5.14** Write `app/schemas/kanji.py` — `KanjiCard` schema (stroke_count, radicals, on_readings, kun_readings, meanings, jlpt_level)
- [ ] **5.15** Write `app/routers/search.py` — `GET /api/search?q=&lang=&mode=` dispatching to `jmdict.search_jmdict` (jp) or `cedict.search_cedict` (cn); returns `list[DictEntry]`
- [ ] **5.16** Write `app/routers/kanji.py` — `GET /api/kanji/{char}`: validate single CJK char, call `jmdict.get_kanji_detail`, return `KanjiCard` 200 or 404
- [ ] **5.17** Verify: `GET /api/search?q=猫&lang=jp` returns ≥ 1 result served entirely from DB; no external HTTP calls in logs

---

## Phase 6 — Vocabulary & History Endpoints

- [ ] **6.1** Write `app/schemas/vocabulary.py` — `SavedWordCreate`, `SavedWord` schemas
- [ ] **6.2** Write `app/routers/vocabulary.py` — `GET /api/vocabulary`, `POST /api/vocabulary` (201/409), `DELETE /api/vocabulary/{id}` (204/403/404)
- [ ] **6.3** Write `app/routers/history.py` — `GET /api/history?lang=&limit=`
- [ ] **6.4** Register vocabulary and history routers in `main.py`
- [ ] **6.5** Verify: OpenAPI docs at `/docs` show all endpoints; vocabulary CRUD works end-to-end

---

## Phase 7 — Caching Layer

- [ ] **7.1** Write `app/services/cache.py` — `TTLCache(maxsize=512, ttl=600)` in-memory layer using `cachetools`
- [ ] **7.2** Implement `get_kanji_cached(char)` — check in-memory cache first, then `kanji_cache` table (filter `expires_at > NOW()`), return data or `None`
- [ ] **7.3** Implement `set_kanji_cache(char, data)` — write to in-memory cache and upsert into `kanji_cache` with `expires_at = NOW() + 30 days`
- [ ] **7.4** Wire cache into kanji endpoint: on miss call `jmdict.get_kanji_detail`, populate both cache levels; on hit skip DB query
- [ ] **7.5** Verify: second request for same kanji is served from in-memory cache (no DB query visible in logs)

---

## Phase 8 — AI Explanation Endpoint (OpenRouter SSE)

- [ ] **8.1** Write `app/routers/explain.py` — `POST /api/explain` accepts `list[TokenResult]`; streams OpenRouter response as SSE via `StreamingResponse(media_type="text/event-stream")`; forwards API key server-side only
- [ ] **8.2** Register explain router in `main.py`
- [ ] **8.3** Verify: `POST /api/explain` streams tokens to client; `OPENROUTER_API_KEY` is never exposed in response headers or body

---

## Phase 9 — Security Hardening

- [ ] **9.1** Add `CORSMiddleware` to `main.py` — `allow_origins=settings.ALLOWED_ORIGINS`, `allow_credentials=True`, methods `GET/POST/DELETE` only
- [ ] **9.2** Add security headers middleware — `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`
- [ ] **9.3** Verify `get_current_user` dependency is applied to every protected route
- [ ] **9.4** Add ownership check in `DELETE /api/vocabulary/{id}` — raise `403` if `word.user_id != current_user.id`
- [ ] **9.5** Add startup validation — raise if `SECRET_KEY` is shorter than 32 characters
- [ ] **9.6** Add input length caps — `AnalyzeRequest.query` max 500 chars, search `q` param max 100 chars (Pydantic `max_length`)
- [ ] **9.7** Implement Redis rate limiter dependency — 60 req/min anonymous, 120 req/min authenticated; return `HTTP 429` with `Retry-After: 60` header
- [ ] **9.8** Apply rate limiter to all public-facing routes
- [ ] **9.9** Add `dependabot.yml` for weekly pip dependency updates
- [ ] **9.10** Verify: CORS rejects unknown origins; rate limiter returns 429 after threshold; security headers present in every response

---

## Phase 10 — Testing

- [ ] **10.1** Write `tests/conftest.py` — async SQLite in-memory engine, `AsyncClient(app=app)` fixture, test user fixture
- [ ] **10.2** Write `tests/test_classifier.py` — unit tests for all 4 `QueryType` branches (KANJI, HANZI, SENTENCE, REVERSE) including edge cases (empty string, mixed scripts)
- [ ] **10.3** Write `tests/test_japanese.py` — unit tests for tokenizer output shape (surface, reading, POS fields present)
- [ ] **10.4** Write `tests/test_chinese.py` — unit tests for segmentation output and pinyin conversion
- [ ] **10.5** Write `tests/test_auth.py` — integration: register (201), duplicate register (409), login (200 + cookie), invalid login (401), refresh (200), expired token (401)
- [ ] **10.6** Write `tests/test_analyze.py` — integration: 200 with complexity, 206 without (< 3 leveled tokens), 400 empty query
- [ ] **10.7** Write `tests/test_vocabulary.py` — integration: list (200), add (201), duplicate (409), delete own (204), delete other user's word (403)
- [ ] **10.8** Write `tests/test_search.py` — integration: JP search hits `jmdict_entries`, CN search hits `cedict_entries`; both return `list[DictEntry]`
- [ ] **10.9** Write `tests/test_kanji.py` — integration: cache miss (DB query), cache hit (no DB query), single char 200, multi-char 400, unknown char 404
- [ ] **10.10** Run `pytest --cov=app --cov-report=term-missing`; ensure line coverage ≥ 67%

---

## Phase 11 — Production Configuration

- [ ] **11.1** Write `entrypoint.sh` — run `alembic upgrade head`, run import scripts idempotently if tables are empty, then exec `uvicorn --workers 4 --proxy-headers`
- [ ] **11.2** Write `docker-compose.prod.yml` — no `.env` file baked in, secrets from environment; Postgres `max_connections=200 shared_buffers=256MB`; Redis `maxmemory 128mb maxmemory-policy allkeys-lru`
- [ ] **11.3** Add health checks to all 3 services in compose (30s interval, 3 retries)
- [ ] **11.4** Configure structured JSON logging (uvicorn `--log-config` or `python-json-logger`)
- [ ] **11.5** Write `README.md` with local setup instructions (prerequisites, `docker compose up`, import commands, test command)
- [ ] **11.6** Verify: `docker compose -f docker-compose.prod.yml up` starts cleanly; `/health` returns 200; migrations and imports run automatically on boot
