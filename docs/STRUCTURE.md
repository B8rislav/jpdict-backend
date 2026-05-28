# Project Structure

Directory-by-directory walkthrough of the backend. Every file listed with its role.

```
backend/
├── app/                  Main application package
├── alembic/              Database migrations
├── scripts/              One-shot data import scripts
├── tests/                Pytest test suite
├── data/                 Downloaded corpus files (gitignored)
├── docs/                 This documentation tree
├── Dockerfile
├── docker-compose.yml
├── docker-compose.prod.yml
├── entrypoint.sh         Container startup: migrations + imports + uvicorn
├── pyproject.toml
├── alembic.ini
├── log_config.json       Uvicorn logging configuration (JSON formatter)
├── Makefile
└── README.md
```

---

## `app/`

### `app/main.py`

FastAPI application entry point. Registers middleware (`CORSMiddleware`, `SecurityHeadersMiddleware`) and all routers. Contains the `GET /health` endpoint and an empty `lifespan` context manager (placeholder for future startup/shutdown hooks).

### `app/core/`

Cross-cutting concerns shared across routers and services.

| File | Role |
|---|---|
| `app/core/config.py` | `Settings` (pydantic-settings). Loads `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `OPENROUTER_API_KEY`, `ALLOWED_ORIGINS` from environment / `.env`. `SECRET_KEY` must be ≥ 32 chars (validated at startup). |
| `app/core/security.py` | JWT helpers (`create_access_token`, `create_refresh_token`, `decode_token`) and bcrypt wrappers (`hash_password`, `verify_password`). HS256, 15-min access TTL, 7-day refresh TTL. |
| `app/core/deps.py` | FastAPI dependencies. `get_current_user()` — decodes Bearer JWT, enforces `type=access`, returns `User` ORM. `paginate()` / `Paginator` — typed page/per_page query params with `.offset` property. |
| `app/core/rate_limit.py` | Redis-backed rate limiter. 60 req/min anonymous (keyed by IP), 120 req/min authenticated (keyed by user UUID). Fails open if Redis is unavailable. |
| `app/core/json_log_formatter.py` | Python `logging.Formatter` subclass that emits structured JSON with `timestamp`, `level`, `logger`, `message`, `exc_info`. |

### `app/db/`

| File | Role |
|---|---|
| `app/db/database.py` | `AsyncEngine` created from `settings.DATABASE_URL`. `async_sessionmaker` with `expire_on_commit=False`. `get_session()` dependency that yields an `AsyncSession` and closes it automatically. |

### `app/models/`

SQLAlchemy ORM models (all mapped to `Base` from `base.py`).

| File | Table | Notes |
|---|---|---|
| `app/models/base.py` | — | `DeclarativeBase` subclass; all models inherit from it. |
| `app/models/user.py` | `users` | `LanguageEnum` (`jp`/`cn`). UUID PK. |
| `app/models/saved_word.py` | `saved_words` | `WordStatusEnum` (`new`/`learning`/`known`). Unique `(user_id, language, expression)`. |
| `app/models/search_history.py` | `search_history` | Records each search query per user. |
| `app/models/kanji_cache.py` | `kanji_cache` | JSONB-serialised `KanjiCard` with `expires_at`. |

### `app/routers/`

One file per endpoint group. Public routers apply `Depends(rate_limit)` at the router level; authenticated routers apply `Depends(get_current_user)` per handler.

| File | Prefix | Endpoints |
|---|---|---|
| `app/routers/auth.py` | `/api/auth` | `POST /register`, `POST /login`, `POST /refresh` |
| `app/routers/analyze.py` | `/api` | `POST /analyze` — NLP tokenization entry point |
| `app/routers/search.py` | `/api` | `GET /search` — JMdict or CC-CEDICT lookup |
| `app/routers/kanji.py` | `/api` | `GET /kanji/search`, `GET /kanji/{char}` |
| `app/routers/reibun.py` | `/api` | `GET /reibun/search/{word_id}` — example sentences |
| `app/routers/vocabulary.py` | `/api/vocabulary` | Full CRUD for saved words (auth required) |
| `app/routers/history.py` | `/api/history` | Record and retrieve search history (auth required) |

See [API.md](API.md) for the full endpoint table with schemas and line numbers.

### `app/schemas/`

Pydantic v2 request/response models.

| File | Schemas |
|---|---|
| `app/schemas/analyze.py` | `AnalyzeRequest`, `TokenResult`, `LevelBreakdown`, `AnalyzeResponse` |
| `app/schemas/auth.py` | `UserCreate`, `UserResponse`, `TokenResponse` |
| `app/schemas/kanji.py` | `KanjiCard` |
| `app/schemas/page.py` | `Page[T]` — generic pagination wrapper with `build()` class method |
| `app/schemas/reibun.py` | `Reibun`, `ReibunSearchResponse` |
| `app/schemas/search.py` | `DictEntry` |
| `app/schemas/vocabulary.py` | `SavedWordCreate`, `SavedWordStatusUpdate`, `SavedWord` |
| `app/schemas/validators.py` | `SafeStr` — strips null bytes, rejects blank strings |

### `app/services/`

Business logic and data access.

| File | Role |
|---|---|
| `app/services/cache.py` | Two-level kanji cache: `TTLCache(maxsize=512, ttl=600)` in memory + `kanji_cache` Postgres table (30-day TTL). Also caches reibun results per `(expression, page, per_page)` in `TTLCache(maxsize=1024, ttl=600)`. |
| `app/services/jmdict.py` | `search_jmdict()` — paginated lookup by kanji forms, reading forms, or English gloss prefix. `get_kanji_detail()` — builds a `KanjiCard` from `kanjidic_entries` + `jmdict_entries`. Contains `KANGXI` dict (radical number → character, 1–214). |
| `app/services/cedict.py` | `search_cedict()` — exact → prefix → trigram-similarity search on `cedict_entries`. Extracts Russian definitions from JSONB, falls back to English. |
| `app/services/pinyin.py` | `convert_pinyin()` — converts numbered pinyin (`wo3`) to diacritic form (`wǒ`). |
| `app/services/reibun.py` | `search_reibun()` — looks up canonical expression for a `jmdict_entries.id`, searches `reibun_entries` by `ILIKE %expression%`, returns paginated results with cache. |

### `app/services/nlp/`

| File | Role |
|---|---|
| `app/services/nlp/classifier.py` | `classify(query, language)` — Unicode-range routing to `QueryType` (KANJI / HANZI / SENTENCE / REVERSE). No external dependencies. |
| `app/services/nlp/japanese.py` | `tokenize_japanese(text)` — SudachiPy mode C tokenizer. Returns surface, dictionary form, katakana reading, POS, JLPT level. Lazy-initialized singleton tokenizer. |
| `app/services/nlp/chinese.py` | `tokenize_chinese(text)` — jieba POS segmentation + pypinyin pinyin. Returns surface, POS, HSK level, diacritic pinyin. |

---

## `alembic/`

| File | Role |
|---|---|
| `alembic/env.py` | Alembic environment; imports `Base.metadata` for autogenerate support. |
| `alembic/script.py.mako` | Migration file template. |
| `alembic/versions/0001_initial_schema.py` | Enable `pgcrypto`, `pg_trgm`; create `users`, `saved_words`, `search_history`, `kanji_cache`; create GIN and btree indexes. |
| `alembic/versions/0002_dictionary_tables.py` | Create `jmdict_entries` and `kanjidic_entries` with GIN array indexes. |
| `alembic/versions/0003_cedict_entries.py` | Create `cedict_entries` with GIN trigram indexes on `simplified` and `traditional`. |
| `alembic/versions/0004_kanji_meanings_ru.py` | Add `meanings_ru TEXT[]` column to `kanjidic_entries`. |
| `alembic/versions/0005_reibun_entries.py` | Create `reibun_entries` with GIN trigram index on `sentence_jp`. |

---

## `scripts/`

One-shot import scripts. All are idempotent (no-op when the target table already has rows). Run in the order shown, or use `make import-all`.

| File | `make` target | Populates |
|---|---|---|
| `scripts/import_jmdict.py` | `import-jmdict` | `jmdict_entries` |
| `scripts/import_kanjidic2.py` | `import-kanjidic` | `kanjidic_entries` |
| `scripts/import_kradfile.py` | `import-kradfile` | `kanjidic_entries.components` (run after kanjidic) |
| `scripts/import_cedict.py` | `import-cedict` | `cedict_entries` |
| `scripts/import_hsk.py` | `import-hsk` | `cedict_entries.hsk_level + definitions.ru` (run after cedict) |
| `scripts/import_kanji_ru.py` | `import-kanji-ru` | `kanjidic_entries.meanings_ru` (run after jmdict + kanjidic) |
| `scripts/import_tatoeba.py` | `import-reibun` | `reibun_entries` |

---

## `tests/`

Pytest test suite. Uses fixtures in `conftest.py` for async DB sessions and test client.

| File | Coverage area |
|---|---|
| `tests/conftest.py` | Fixtures: async engine, test session, `AsyncClient` |
| `tests/test_auth.py` | Register, login, refresh, duplicate email, bad credentials |
| `tests/test_analyze.py` | Japanese and Chinese analysis, JLPT/HSK breakdown, 206 on sparse results |
| `tests/test_classifier.py` | All `QueryType` branches, edge cases |
| `tests/test_japanese.py` | SudachiPy tokenization output |
| `tests/test_chinese.py` | jieba segmentation, pinyin output |
| `tests/test_search.py` | JMdict and CC-CEDICT search, pagination |
| `tests/test_kanji.py` | Kanji search and detail, cache behavior |
| `tests/test_vocabulary.py` | CRUD, duplicate word, ownership checks |
| `tests/test_injection.py` | Null-byte and SQL injection probes via `SafeStr` |
| `tests/test_security.py` | JWT tamper, expired token, wrong type, rate limit boundary |

---

## `data/`

Downloaded corpus files. Not committed to git; obtained by running the import scripts or `make import-all`.

| File | Used by |
|---|---|
| `JMdict.gz` | `import_jmdict.py` |
| `kanjidic2.xml.gz` | `import_kanjidic2.py` |
| `kradfile.gz` | `import_kradfile.py` |
| `cedict_ts.u8.gz` | `import_cedict.py` |
| `hsk.json` | `import_hsk.py` |
| `jpn_sentences.tsv.bz2` | `import_tatoeba.py` |
| `rus_sentences.tsv.bz2` | `import_tatoeba.py` |
| `eng_sentences.tsv.bz2` | `import_tatoeba.py` |
| `tatoeba_links.tar.bz2` | `import_tatoeba.py` |
