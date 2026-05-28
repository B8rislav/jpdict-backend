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

- [x] **3.1** Write `app/core/security.py`: `hash_password`, `verify_password` (bcrypt cost 12), `create_access_token` (15 min), `create_refresh_token` (7 days), `decode_token`
- [x] **3.2** Write Pydantic schemas in `app/schemas/auth.py`: `UserCreate`, `UserResponse`, `TokenResponse`
- [x] **3.3** Write `app/routers/auth.py` — `POST /api/auth/register` (201/409), `POST /api/auth/login` (200 + httpOnly refresh cookie), `POST /api/auth/refresh` (200/401)
- [x] **3.4** Write `get_current_user` FastAPI dependency — validates Bearer token, returns `User` ORM object; used on all protected routes
- [x] **3.5** Register auth router in `main.py`
- [x] **3.6** Verify: register → login → call protected endpoint → refresh flow works end-to-end

---

## Phase 4 — NLP Module

- [x] **4.1** Write `app/services/nlp/classifier.py` — `QueryType` enum (KANJI/HANZI/SENTENCE/REVERSE), Unicode range constants, `classify(query, language)` function
- [x] **4.2** Write `app/services/nlp/japanese.py` — init SudachiPy tokenizer (mode C, SudachiDict-core), `tokenize_japanese(text) -> list[TokenResult]` with surface, dictionary form, reading (katakana), POS, JLPT level
- [x] **4.3** Write `app/services/nlp/chinese.py` — HanLP singleton (lazy init), `tokenize_chinese(text) -> list[TokenResult]` with word segmentation, POS, pinyin (pypinyin), HSK level; support simplified + traditional
- [x] **4.4** Write Pydantic schemas in `app/schemas/analyze.py`: `AnalyzeRequest`, `TokenResult`, `AnalyzeResponse`
- [x] **4.5** Write `app/routers/analyze.py` — `POST /api/analyze`: 200 (full result), 206 (level_breakdown not computable — < 3 leveled tokens), 400 (empty/invalid query)
- [x] **4.6** Register analyze router in `main.py`
- [x] **4.7** Verify: `POST /api/analyze {"query":"日本語","language":"jp"}` returns tokens with readings, POS, JLPT levels, and level_breakdown

---

## Phase 5 — Dictionary Research & DB Integration

> Goal: replace all external dictionary API calls with data loaded into PostgreSQL at startup.
> No runtime HTTP calls to Jisho or CC-CEDICT file parsing — everything served from DB.

### 5a — Japanese dictionary (JMdict replacement for Jisho)

- [x] **5.1** Research open Japanese dictionary sources — **chosen**: JMdict (full multilingual XML, CC BY-SA 4.0) for EN+RU glosses + JLPT via `<misc>`; KANJIDIC2 for kanji details; KRADFILE for component decomposition
- [x] **5.2** Write `scripts/import_jmdict.py` — downloads `JMdict.gz` (full multilingual, not `_e`), parses XML with `lxml` (`load_dtd=True` for entity resolution), extracts EN + RU glosses, `pos`, JLPT level from `<misc>`, common-word flag; batch-inserts via asyncpg
- [x] **5.3** Add Alembic migration `0002_dictionary_tables.py` for `jmdict_entries` table (entry_id unique, kanji_forms/reading_forms GIN-indexed, senses JSONB, jlpt_level, common)
- [x] **5.4** Write `scripts/import_kanjidic2.py` — downloads `kanjidic2.xml.gz`, parses character/stroke_count/grade/freq/on_readings/kun_readings/meanings_en/radical_number/jlpt_level; KRADFILE component decomposition added by `import_kradfile.py`
- [x] **5.5** Migration `0002` also creates `kanjidic_entries` table: `character` TEXT PK, `stroke_count`, `jlpt_level`, `grade`, `frequency`, `on_readings`, `kun_readings`, `meanings_en`, `radical_number`, `components TEXT[]` (from KRADFILE)
- [ ] **5.6** Write `app/services/jmdict.py` — `search_jmdict(query, mode) -> list[DictEntry]` querying `jmdict_entries` via GIN index; `get_kanji_detail(char) -> KanjiCard` from `kanjidic_entries`
- [x] **5.7** Added `make import-jmdict`, `make import-kanjidic`, `make import-kradfile`, `make import-all` targets; all scripts are idempotent (skip if table already populated); also added `scripts/import_kradfile.py` for KRADFILE component decomposition

### 5b — Chinese dictionary (CC-CEDICT into DB)

- [x] **5.8** Research open Chinese dictionary sources — **chosen**: CC-CEDICT (MDBG, CC BY-SA 4.0) for simplified+traditional+pinyin+EN glosses; HSK 1-6 wordlist from nickelc/hsk-level (CC0) for level data; `definitions_en` + `definitions_ru` columns mirror JMdict EN+RU pattern
- [x] **5.9** Write `scripts/import_cedict.py` — downloads `cedict_ts.u8.gz`, parses line-by-line regex, extracts `traditional`, `simplified`, `pinyin`, `definitions_en`; bulk-inserts into `cedict_entries`; idempotent
- [x] **5.10** Added Alembic migration `0003_cedict_entries.py` for `cedict_entries`: `id`, `traditional`, `simplified`, `pinyin`, `definitions_en TEXT[]`, `definitions_ru TEXT[]`, `hsk_level`; GIN trigram indexes on `simplified` and `traditional`; index on `hsk_level`
- [x] **5.11** Write `app/services/cedict.py` — `search_cedict(query, lang, session) -> list[DictEntry]` — exact → prefix → trigram ranking; `lang=cn_traditional` matches traditional column; returns `definitions_ru` when populated, falls back to `definitions_en`
- [x] **5.12** Write `scripts/import_hsk.py` — downloads nickelc/hsk-level JSON, supports flat `{word: level}` and `{level: [words]}` formats; UPDATEs `hsk_level` on matching `cedict_entries` rows; idempotent

### 5c — Wire into routers

- [x] **5.13** Write `app/schemas/search.py` — `DictEntry` schema
- [x] **5.14** Write `app/schemas/kanji.py` — `KanjiCard` schema (stroke_count, radicals, on_readings, kun_readings, meanings, jlpt_level)
- [x] **5.15** Write `app/routers/search.py` — `GET /api/search?q=&lang=&mode=` dispatching to `jmdict.search_jmdict` (jp) or `cedict.search_cedict` (cn); returns `list[DictEntry]`
- [x] **5.16** Write `app/routers/kanji.py` — `GET /api/kanji/{char}`: validate single CJK char, call `jmdict.get_kanji_detail`, return `KanjiCard` 200 or 404
- [x] **5.17** Verify: `GET /api/search?q=猫&lang=jp` returns ≥ 1 result served entirely from DB; no external HTTP calls in logs

---

## Phase 6 — Vocabulary & History Endpoints

- [x] **6.1** Write `app/schemas/vocabulary.py` — `SavedWordCreate`, `SavedWord` schemas
- [x] **6.2** Write `app/routers/vocabulary.py` — `GET /api/vocabulary`, `POST /api/vocabulary` (201/409), `DELETE /api/vocabulary/{id}` (204/403/404)
- [x] **6.3** Write `app/routers/history.py` — `GET /api/history?lang=&limit=`
- [x] **6.4** Register vocabulary and history routers in `main.py`
- [x] **6.5** Verify: OpenAPI docs at `/docs` show all endpoints; vocabulary CRUD works end-to-end

---

## Phase 7 — Caching Layer

- [x] **7.1** Write `app/services/cache.py` — `TTLCache(maxsize=512, ttl=600)` in-memory layer using `cachetools`
- [x] **7.2** Implement `get_kanji_cached(char)` — check in-memory cache first, then `kanji_cache` table (filter `expires_at > NOW()`), return data or `None`
- [x] **7.3** Implement `set_kanji_cache(char, data)` — write to in-memory cache and upsert into `kanji_cache` with `expires_at = NOW() + 30 days`
- [x] **7.4** Wire cache into kanji endpoint: on miss call `jmdict.get_kanji_detail`, populate both cache levels; on hit skip DB query
- [x] **7.5** Verify: second request for same kanji is served from in-memory cache (no DB query visible in logs)

---

## Phase 8 — AI Explanation Endpoint (OpenRouter SSE)

- [ ] **8.1** Write `app/routers/explain.py` — `POST /api/explain` accepts `list[TokenResult]`; streams OpenRouter response as SSE via `StreamingResponse(media_type="text/event-stream")`; forwards API key server-side only
- [ ] **8.2** Register explain router in `main.py`
- [ ] **8.3** Verify: `POST /api/explain` streams tokens to client; `OPENROUTER_API_KEY` is never exposed in response headers or body

---

## Phase 9 — Security Hardening

### 9a — Injection protection

- [x] **9.1** Audit all DB queries — confirm zero raw SQL with user input; every query must go through SQLAlchemy ORM or explicit `text()` with bound parameters
- [x] **9.2** Audit search query path — `GET /api/search?q=` passes `q` only as a bound parameter into GIN index lookup, never string-interpolated into SQL
- [x] **9.3** Add Pydantic validators on all string inputs that touch the DB: strip null bytes (`\x00`), reject strings that are purely whitespace
- [x] **9.4** Add input length caps — `AnalyzeRequest.query` max 500 chars, search `q` max 100 chars, vocabulary `expression` max 100 chars (Pydantic `max_length`)
- [x] **9.5** Validate `GET /api/kanji/{char}` path parameter — reject anything that is not a single CJK Unicode character before it reaches the DB
- [x] **9.6** Write `tests/test_injection.py` — send payloads like `' OR 1=1--`, `; DROP TABLE users;--`, `<script>`, null bytes to every public endpoint; assert all return 400 or safe data, never 500

### 9b — Authentication & access control

- [x] **9.7** Verify `get_current_user` dependency is applied to every protected route
- [x] **9.8** Add ownership check in `DELETE /api/vocabulary/{id}` — raise `403` if `word.user_id != current_user.id`
- [x] **9.9** Add startup validation — raise on boot if `SECRET_KEY` is shorter than 32 characters

### 9c — Transport & headers

- [x] **9.10** Add `CORSMiddleware` to `main.py` — `allow_origins=settings.ALLOWED_ORIGINS`, `allow_credentials=True`, methods `GET/POST/DELETE` only
- [x] **9.11** Add security headers middleware — `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`

### 9d — Rate limiting & dependencies

- [x] **9.12** Implement Redis rate limiter dependency — 60 req/min anonymous, 120 req/min authenticated; return `HTTP 429` with `Retry-After: 60` header
- [x] **9.13** Apply rate limiter to all public-facing routes
- [x] **9.14** Add `dependabot.yml` for weekly pip dependency updates
- [x] **9.15** Verify: CORS rejects unknown origins; injection payloads return 400; rate limiter returns 429 after threshold; security headers present in every response

---

## Phase 10 — Testing

- [x] **10.1** Write `tests/conftest.py` — async SQLite in-memory engine, `AsyncClient(app=app)` fixture, test user fixture
- [x] **10.2** Write `tests/test_classifier.py` — unit tests for all 4 `QueryType` branches (KANJI, HANZI, SENTENCE, REVERSE) including edge cases (empty string, mixed scripts)
- [x] **10.3** Write `tests/test_japanese.py` — unit tests for tokenizer output shape (surface, reading, POS fields present)
- [x] **10.4** Write `tests/test_chinese.py` — unit tests for segmentation output and pinyin conversion
- [x] **10.5** Write `tests/test_auth.py` — integration: register (201), duplicate register (409), login (200 + cookie), invalid login (401), refresh (200), expired token (401)
- [x] **10.6** Write `tests/test_analyze.py` — integration: 200 with complexity, 206 without (< 3 leveled tokens), 400 empty query
- [x] **10.7** Write `tests/test_vocabulary.py` — integration: list (200), add (201), duplicate (409), delete own (204), delete other user's word (403)
- [x] **10.8** Write `tests/test_search.py` — integration: JP search hits `jmdict_entries`, CN search hits `cedict_entries`; both return `list[DictEntry]`
- [x] **10.9** Write `tests/test_kanji.py` — integration: cache miss (DB query), cache hit (no DB query), single char 200, multi-char 400, unknown char 404
- [x] **10.10** Run `pytest --cov=app --cov-report=term-missing`; ensure line coverage ≥ 67%

---

## Phase 11 — Production Configuration

- [x] **11.1** Write `entrypoint.sh` — run `alembic upgrade head`, run import scripts idempotently if tables are empty, then exec `uvicorn --workers 4 --proxy-headers`
- [x] **11.2** Write `docker-compose.prod.yml` — no `.env` file baked in, secrets from environment; Postgres `max_connections=200 shared_buffers=256MB`; Redis `maxmemory 128mb maxmemory-policy allkeys-lru`
- [x] **11.3** Add health checks to all 3 services in compose (30s interval, 3 retries)
- [x] **11.4** Configure structured JSON logging (uvicorn `--log-config` or `python-json-logger`)
- [x] **11.5** Write `README.md` with local setup instructions (prerequisites, `docker compose up`, import commands, test command)
- [x] **11.6** Verify: `docker compose -f docker-compose.prod.yml up` starts cleanly; `/health` returns 200; migrations and imports run automatically on boot

---

## Phase 12 — Russian Kanji Translations

> Goal: replace the English-only kanji meanings rendered on the frontend kanji card with Russian glosses where available, falling back to English when no Russian translation exists.
> Current state: `kanjidic_entries.meanings_en` is populated from KANJIDIC2 and returned verbatim by `app/services/jmdict.py::get_kanji_detail`; the frontend has no Russian source to display.

- [x] **12.1** Research open Russian kanji meaning sources — candidates: Warodai (Yarxi/JARDIC, Japanese-Russian dictionary, free non-commercial), kanjivg-derived community translations, ru.kanjiapi.dev or similar community-maintained JSON dumps, JLPT N5–N1 Russian wordlists. Pick a source whose license is compatible with this project and document the choice in `docs/DATA_SOURCES.md` (created in Phase 14)
- [x] **12.2** Add Alembic migration `0004_kanji_meanings_ru.py` — add `meanings_ru TEXT[] NOT NULL DEFAULT '{}'` column to `kanjidic_entries`; backfill is empty until import runs
- [x] **12.3** Write `scripts/import_kanji_ru.py` — download/parse chosen source, normalise to `{character: [ru_meaning, ...]}`, bulk-UPDATE `kanjidic_entries.meanings_ru` on matching `character`; idempotent (re-run replaces existing values for matched rows)
- [x] **12.4** Add `make import-kanji-ru` target and include it in `make import-all`
- [x] **12.5** Extend `KanjiCard` schema in `app/schemas/kanji.py` — add `meanings_ru: list[str]` field (keep existing `meanings` for backwards compatibility, populate from RU when present, else EN)
- [x] **12.6** Update `app/services/jmdict.py::get_kanji_detail` — select `meanings_ru` alongside `meanings_en`; populate `KanjiCard.meanings_ru` from the new column; `meanings` (the legacy field) becomes `meanings_ru if meanings_ru else meanings_en`
- [x] **12.7** Update OpenAPI examples for `GET /api/kanji/{char}` to show the new `meanings_ru` field
- [x] **12.8** Verify: `GET /api/kanji/猫` returns non-empty `meanings_ru`; frontend kanji card shows Russian text instead of English for kanji that have a Russian translation; kanji without a Russian translation still render English without breaking

---

## Phase 13 — Example Sentences (Reibun) in Russian

> Goal: make `GET /api/reibun/search/{word_id}` return real example sentences instead of the current empty stub, preferring Russian translations and falling back to English.
> Current state: `app/routers/reibun.py` returns `{"result_count": 0, ..., "reibuns": []}` unconditionally.

- [x] **13.1** Research open parallel corpora with Japanese sentences and Russian/English translations — primary candidate: **Tatoeba** (CC BY 2.0 FR, sentence + links + translations CSV dumps with `jpn↔rus` and `jpn↔eng` pairs); secondary: **OpenSubtitles ja-ru** via OPUS, Reflex/Reibun corpus. Pick Tatoeba unless a better source is identified; record decision in `docs/DATA_SOURCES.md`
- [x] **13.2** Add Alembic migration `0005_reibun_entries.py` creating `reibun_entries` table: `id BIGSERIAL PK`, `sentence_jp TEXT NOT NULL`, `reading_jp TEXT NULL` (furigana/kana form when available), `translation_ru TEXT NULL`, `translation_en TEXT NULL`, `source TEXT NOT NULL` (e.g. `'tatoeba'`), `source_sentence_id BIGINT NULL`; GIN trigram index on `sentence_jp` for substring lookup, plain B-tree on `source_sentence_id`
- [x] **13.3** Write `scripts/import_tatoeba.py` — download Tatoeba `sentences.tar.bz2` and `links.csv` (or per-language sentence files), filter to `jpn` source sentences, join translations to `rus` and `eng`, bulk-insert into `reibun_entries`; idempotent (skip when table already populated or upsert by `(source, source_sentence_id)`)
- [x] **13.4** Add `make import-reibun` target and include it in `make import-all`
- [x] **13.5** Write `app/schemas/reibun.py` — `Reibun` (id, sentence_jp, reading_jp, translation: str picked server-side, translation_lang: 'ru'|'en'), `ReibunSearchResponse` (result_count, pg, perPage, reibuns) matching existing frontend contract
- [x] **13.6** Write `app/services/reibun.py::search_reibun(expression, session, page, per_page)` — look up the canonical expression for `word_id` from `jmdict_entries`, then `SELECT ... FROM reibun_entries WHERE sentence_jp ILIKE '%' || :expr || '%' ORDER BY length(sentence_jp) ASC LIMIT/OFFSET` (shorter sentences first as a relevance heuristic); return tuple `(items, total_count)`. Prefer `translation_ru`; fall back to `translation_en` when RU is `NULL`; set `translation_lang` accordingly
- [x] **13.7** Replace the stub body of `app/routers/reibun.py::reibun_search` — call `search_reibun`, wrap in `ReibunSearchResponse`; keep current path and pagination shape (`pg`, `perPage`) so the frontend keeps working
- [x] **13.8** Optional: add an in-memory `TTLCache` layer in `app/services/cache.py` for `(expression, page)` → `ReibunSearchResponse` to keep popular lookups cheap
- [x] **13.9** Verify: `GET /api/reibun/search/<id-for-猫>` returns ≥ 1 example sentence; at least some entries have `translation_lang == "ru"`; entries with no Russian translation cleanly return `translation_lang == "en"`; pagination (`pg=2`) works

---

## Phase 14 — Architecture & Project Documentation

> Goal: a self-contained `backend/docs/` tree that lets a new contributor (or future me) navigate the codebase without re-reading every file. Keep prose tight: each doc should be skimmable in under five minutes.

- [x] **14.1** Create `backend/docs/` directory and `backend/docs/README.md` — index linking every doc below with a one-line description per entry
- [x] **14.2** Write `docs/ARCHITECTURE.md` — high-level overview: request lifecycle (FastAPI → router → service → SQLAlchemy → Postgres), where the in-memory + Postgres cache sits, where the NLP pipeline plugs in, where auth middleware runs, where the SSE explain endpoint terminates; one ASCII diagram of the components is enough
- [x] **14.3** Write `docs/STRUCTURE.md` — directory-by-directory walkthrough of `app/`, `scripts/`, `alembic/`, `tests/`, `data/`; for each folder list its purpose and the role of each file (e.g. `app/core/rate_limit.py` — Redis-backed leaky bucket, applied per-router via `Depends(rate_limit)`)
- [x] **14.4** Write `docs/DATA_SOURCES.md` — one section per imported corpus (JMdict, KANJIDIC2, KRADFILE, CC-CEDICT, HSK wordlist, Russian kanji source from Phase 12, Tatoeba from Phase 13); columns per source: license, download URL, target table, import script, `make` target, refresh cadence
- [x] **14.5** Write `docs/API.md` — table of every public endpoint (method, path, auth required, request/response schema name, rate limit class); link each row to the router file with `app/routers/<file>.py:<lineno>`; mark endpoints still backed by stubs (e.g. pre-Phase 13 `reibun`)
- [x] **14.6** Write `docs/DATABASE.md` — ERD-style summary of every table: columns, constraints, indexes, FK relations; flag GIN/trigram indexes explicitly; cross-link the Alembic migration that introduced each table
- [x] **14.7** Write `docs/NLP.md` — explain `classifier` (Unicode-range routing), `japanese` (SudachiPy mode C + JLPT lookup), `chinese` (HanLP + pypinyin + HSK lookup); list known caveats (mixed-script queries, traditional vs simplified detection)
- [x] **14.8** Write `docs/SECURITY.md` — summarise Phase 9: where Pydantic validators live, what `get_current_user` guarantees, how the rate limiter keys requests, which headers the security middleware adds; describe the threat model in two paragraphs
- [x] **14.9** Write `docs/RUNBOOK.md` — operational recipes: rebuild local DB from scratch, re-run a single import script, rotate `SECRET_KEY`, drain the cache, inspect rate-limiter state in Redis, tail JSON logs
- [x] **14.10** Cross-link from `backend/README.md` — add a "Documentation" section pointing to `docs/README.md` and the most-used docs (ARCHITECTURE, STRUCTURE, RUNBOOK)
- [x] **14.11** Verify: every Markdown link in `docs/` resolves (no 404s); every file path mentioned in `docs/STRUCTURE.md` actually exists; every endpoint listed in `docs/API.md` appears in the running `/docs` OpenAPI schema

---

## Phase 15 — Reverse Search (English/Russian → JP/CN)

> Goal: make `GET /api/search?q=<english-or-russian>&lang=<jp|cn>` return real dictionary entries instead of an empty list. Today `q=a cat&lang=jp` returns `[]` because the JMdict gloss branch in `app/services/jmdict.py::search_jmdict` only does a left-anchored `LIKE :val || '%'` — `"a cat"` (with the article) matches no gloss prefix, and bare `"cat"` only catches entries whose first gloss starts with `cat`. CC-CEDICT has no reverse-search branch at all in `app/services/cedict.py::search_cedict`.
> Current state: `app/services/nlp/classifier.py::classify` already returns `QueryType.REVERSE` for non-CJK queries, but no service-layer code consumes that signal.

### 15a — Query normalisation

- [x] **15.1** Write `app/services/search/normalize.py::normalize_reverse_query(q)` — trim, lowercase, collapse internal whitespace, strip leading English articles (`a `, `an `, `the `) and trailing punctuation, detect script (`'ru'` if any Cyrillic char, else `'en'`); return `NormalizedQuery(text, script, tokens: list[str])`
- [x] **15.2** Add a unit test in `tests/test_normalize.py` covering: `"a cat"` → `text="cat"`, `"The Cats"` → `text="cats"`, `"кошка"` → `script="ru"`, `"to be"` → tokens `["to","be"]`, empty/whitespace → raises `ValueError`

### 15b — JMdict reverse search

- [x] **15.3** Extend `app/services/jmdict.py` with `search_jmdict_reverse(normalized, session, limit, offset) -> tuple[list[DictEntry], int]` — three-tier ranked query over `jmdict_entries.senses` JSONB:
  1. **Exact gloss match** (`g = :text`) — rank 0
  2. **Word-boundary match** (`g ~* ('\m' || :text || '\M')`) — rank 1, catches `"cat"` inside `"feline (cat)"`
  3. **Prefix match** (`g ILIKE :text || '%'`) — rank 2, current behaviour kept as fallback

  Pick the RU sense array when `normalized.script == 'ru'`, else EN. Order `rank ASC, common DESC, jlpt_level ASC NULLS LAST`. Return at most `limit` rows.
- [x] **15.4** Add a GIN trigram expression index in a new Alembic migration `0006_jmdict_reverse_indexes.py` over the flattened gloss text — concretely either (a) add generated columns `senses_glosses_en TEXT` / `senses_glosses_ru TEXT` materialised from the JSONB and index them with `gin_trgm_ops` (preferred — backfill from existing rows in the same migration), or (b) precompute the flat text in the importer (faster query, slight write cost)
- [x] **15.5** Update `scripts/import_jmdict.py` to populate the new flat gloss columns at insert time so re-import keeps them in sync

### 15c — CC-CEDICT reverse search

- [x] **15.6** Extend `app/services/cedict.py` with `search_cedict_reverse(normalized, lang, session, limit, offset) -> tuple[list[dict], int]` — same three-tier ranking applied against `definitions_ru` (if `script == 'ru'`) else `definitions_en`; tie-break by `hsk_level ASC NULLS LAST`, then `id ASC` for stability
- [x] **15.7** Migration `0006` also adds GIN trigram expression indexes over `array_to_string(definitions_en, ' ')` and `array_to_string(definitions_ru, ' ')` on `cedict_entries`, or materialised flat-text columns following whichever pattern was chosen in 15.4

### 15d — Router wiring

- [x] **15.8** In `app/routers/search.py::search`, call `classifier.classify(q, lang)`; when the result is `QueryType.REVERSE`, dispatch to `search_jmdict_reverse` (for `lang=jp`) or `search_cedict_reverse` (for `lang=cn` / `lang=cn_traditional`); otherwise keep the existing forward path. The response shape (`Page[DictEntry]`) stays identical so the frontend needs no changes
- [x] **15.9** Keep the existing forward-search code paths untouched — reverse search is an additional branch, not a rewrite of the current behaviour

### 15e — Tests & verification

- [x] **15.10** Extend `tests/test_search.py` — assert `GET /api/search?q=cat&lang=jp` returns ≥ 1 entry whose headword/reading corresponds to `猫`; `q=a cat&lang=jp` returns the same entry (article stripped); `q=кошка&lang=jp` returns the same entry (Russian gloss path); `q=cat&lang=cn` returns ≥ 1 entry whose simplified form is `猫`
- [ ] **15.11** Verify: `EXPLAIN ANALYZE` on a representative reverse query shows the GIN trigram index is used (no full table scan); response time on a warm cache is under ~50 ms for typical single-word queries; frontend "a cat" search renders a result list instead of an empty state
