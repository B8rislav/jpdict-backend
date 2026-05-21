# Backend Development Plan — JpDict

Python 3.11 · FastAPI 0.111 · PostgreSQL 15 · Redis 7 · Docker

---

## Phase 1 — Project Skeleton & Environment

**Goal:** Runnable `uvicorn` server with health endpoint and Docker Compose wiring.

### Tasks

- [ ] Init repo, add `.gitignore` (Python, `.env`, `__pycache__`)
- [ ] Create `pyproject.toml` (or `requirements.txt`) with pinned deps:
  ```
  fastapi==0.111.*
  uvicorn[standard]==0.29.*
  sqlalchemy[asyncio]==2.0.*
  asyncpg==0.29.*
  alembic==1.13.*
  pydantic-settings==2.2.*
  python-jose[cryptography]==3.3.*
  passlib[bcrypt]==1.7.*
  httpx==0.27.*
  cachetools==5.3.*
  redis==5.0.*
  pytest==8.2.*
  pytest-asyncio==0.23.*
  sudachipy==0.6.*
  sudachidict-core
  hanlp==2.1.*
  pypinyin==0.51.*
  ```
- [ ] `backend/app/main.py` — FastAPI instance, lifespan context manager, `GET /health`
- [ ] `backend/app/core/config.py` — `Settings` via `pydantic-settings` (env vars: `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `JISHO_BASE_URL`, `OPENROUTER_API_KEY`)
- [ ] `docker-compose.yml` with 4 services:

  | Service    | Image              | Port  |
  |------------|--------------------|-------|
  | `db`       | postgres:15-alpine | 5432  |
  | `cache`    | redis:7-alpine     | 6379  |
  | `backend`  | `./backend`        | 8000  |
  | `frontend` | `./frontend`       | 3000  |

- [ ] `backend/Dockerfile` (multi-stage: builder → runtime)
- [ ] `.env.example` documenting all required variables

### Done when
`docker compose up` starts all services; `GET /health` returns `{"status": "ok"}`.

---

## Phase 2 — Database Schema & ORM Models

**Goal:** All tables created via Alembic, models usable in async sessions.

### Tasks

- [ ] `backend/app/db/database.py` — async engine + `AsyncSession` factory via `asyncpg`
  ```python
  engine = create_async_engine(settings.DATABASE_URL, echo=False)
  async_session = async_sessionmaker(engine, expire_on_commit=False)
  ```
- [ ] `backend/app/models/` — one file per model, all with `UUID` PK:

  | Model           | Key columns                                                                 |
  |-----------------|-----------------------------------------------------------------------------|
  | `User`          | `id`, `email` (unique), `hashed_password`, `language` enum, `created_at`   |
  | `SavedWord`     | `id`, `user_id` FK, `language`, `expression`, `reading`, `meaning`, `jlpt_level`, `hsk_level`, `status` enum (`new/learning/known`), `added_at` |
  | `SearchHistory` | `id`, `user_id` FK, `language`, `query`, `query_type`, `searched_at`        |
  | `KanjiCache`    | `id`, `character` (unique), `data` JSONB, `cached_at`, `expires_at`         |

- [ ] Enable PostgreSQL extensions in first Alembic migration:
  ```sql
  CREATE EXTENSION IF NOT EXISTS "pgcrypto";
  CREATE EXTENSION IF NOT EXISTS "pg_trgm";
  ```
- [ ] DDL for `saved_words` (exact from thesis):
  ```sql
  CREATE TYPE language_enum AS ENUM ('jp', 'cn');
  CREATE TYPE word_status AS ENUM ('new', 'learning', 'known');
  CREATE TABLE saved_words (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      language language_enum NOT NULL,
      expression TEXT NOT NULL,
      reading TEXT NOT NULL,
      meaning TEXT NOT NULL,
      jlpt_level SMALLINT CHECK (jlpt_level BETWEEN 1 AND 5),
      hsk_level  SMALLINT CHECK (hsk_level  BETWEEN 1 AND 6),
      status word_status NOT NULL DEFAULT 'new',
      added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      CONSTRAINT uq_user_word UNIQUE (user_id, language, expression)
  );
  CREATE INDEX idx_saved_words_user_lang ON saved_words (user_id, language);
  CREATE INDEX idx_saved_words_expression_trgm ON saved_words USING GIN (expression gin_trgm_ops);
  ```
- [ ] Alembic init (`alembic init alembic`), configure `env.py` for async engine
- [ ] Generate and apply initial migration: `alembic upgrade head`

### Done when
`alembic upgrade head` runs cleanly; all tables and indexes exist in the `db` container.

---

## Phase 3 — Authentication

**Goal:** Register/login endpoints issue JWTs; protected routes reject missing/expired tokens.

### Tasks

- [ ] `backend/app/core/security.py`:
  - `hash_password(plain)` / `verify_password(plain, hashed)` — passlib bcrypt, cost factor 12
  - `create_access_token(sub, exp=15min)` — python-jose, HS256
  - `create_refresh_token(sub, exp=7days)`
  - `decode_token(token)` → payload or raise `HTTPException 401`

- [ ] `backend/app/routers/auth.py`:

  | Endpoint | Body | Returns |
  |----------|------|---------|
  | `POST /api/auth/register` | `{email, password, language}` | `UserResponse` 201 |
  | `POST /api/auth/login` | `{email, password}` | `{access_token}` 200 + `refresh_token` httpOnly cookie |
  | `POST /api/auth/refresh` | cookie | `{access_token}` 200 / 401 |

- [ ] `get_current_user` FastAPI dependency — validates Bearer token, returns `User` ORM object
- [ ] Pydantic schemas: `UserCreate`, `UserResponse`, `TokenResponse`

### Done when
Register → login → call protected endpoint → refresh flow works end-to-end with `httpx` test.

---

## Phase 4 — NLP Module

**Goal:** `POST /api/analyze` returns tokenized + annotated results for Japanese and Chinese input.

### Directory layout
```
backend/app/services/nlp/
├── classifier.py   # query type heuristic
├── japanese.py     # SudachiPy pipeline
└── chinese.py      # HanLP + pypinyin pipeline
```

### 4a — Classifier

```python
class QueryType(str, Enum):
    KANJI = 'kanji'
    HANZI = 'hanzi'
    SENTENCE = 'sentence'
    REVERSE = 'reverse'

HIRAGANA   = range(0x3040, 0x30A0)
KATAKANA   = range(0x30A0, 0x3100)
CJK_UNIFIED = range(0x4E00, 0xA000)

def classify(query: str, language: str) -> QueryType:
    q = query.strip()
    if not q:
        raise ValueError('Empty query')
    has_jp_chars = any(_is_japanese_char(c) for c in q)
    has_cjk     = any(_is_cjk(c) for c in q)
    n = len(q)
    if language == 'jp':
        if not has_jp_chars:
            return QueryType.REVERSE
        return QueryType.KANJI if n <= 2 else QueryType.SENTENCE
    if language == 'cn':
        if not has_cjk:
            return QueryType.REVERSE
        return QueryType.HANZI if n <= 2 else QueryType.SENTENCE
    return QueryType.REVERSE
```

### 4b — Japanese pipeline (`japanese.py`)

- [ ] Init `SudachiPy` tokenizer with `SudachiDict-core`, mode C (largest compounds)
- [ ] `tokenize_japanese(text) -> list[TokenResult]`:
  - Surface form, dictionary form, reading (katakana), part-of-speech
  - JLPT level lookup (static dict or DB query)
- [ ] Normalization modes: expose A / B / C via optional param

### 4c — Chinese pipeline (`chinese.py`)

- [ ] Init HanLP 2.1 pipeline at module import (lazy, thread-safe singleton)
- [ ] `tokenize_chinese(text) -> list[TokenResult]`:
  - Word segmentation, POS tags
  - Pinyin via `pypinyin` (tone marks + numeric)
  - HSK level lookup
- [ ] Support both simplified and traditional characters

### 4d — Complexity algorithm

Median JLPT/HSK level across tokens that have a non-null level, requiring ≥ 3 such tokens:
```python
def compute_complexity(tokens: list[TokenResult]) -> int | None:
    levels = [t.level for t in tokens if t.level is not None]
    if len(levels) < 3:
        return None
    return statistics.median(levels)
```

### 4e — Analyze router (`routers/analyze.py`)

`POST /api/analyze` — `AnalyzeRequest{query, language}` → `AnalyzeResponse`

Response codes:
- `200` full result
- `206` partial (complexity not computable, < 3 tokens with levels)
- `400` empty / invalid query

### Done when
`POST /api/analyze` with `{"query":"日本語","language":"jp"}` returns tokens with readings, POS, JLPT levels, and complexity score.

---

## Phase 5 — Dictionary & Kanji Endpoints

**Goal:** Search and kanji detail endpoints return structured data.

### Tasks

- [ ] `routers/search.py` — `GET /api/search?q=&lang=&mode=`
  - Delegates to Jisho (JP) or CC-CEDICT (CN)
  - Returns `list[DictEntry]`

- [ ] `routers/kanji.py` — `GET /api/kanji/{char}`
  - Single CJK character validation (reject multi-char)
  - Returns `KanjiCard` with strokes, radicals, readings, JLPT level
  - `404` if not found

- [ ] `routers/vocabulary.py` — protected routes:

  | Method | URL | Description |
  |--------|-----|-------------|
  | `GET`  | `/api/vocabulary` | List saved words for current user |
  | `POST` | `/api/vocabulary` | Save a word (`SavedWordCreate` body) |
  | `DELETE` | `/api/vocabulary/{id}` | Delete by UUID (403 if not owner) |

- [ ] `routers/history.py` — `GET /api/history?lang=&limit=`
  - Returns recent `SearchHistory` for current user

### Done when
All 5 route files registered in `main.py`; OpenAPI docs at `/docs` show all 11 endpoints.

---

## Phase 6 — Caching Layer

**Goal:** Two-level cache reduces latency and external API calls.

### Architecture

```
Request → in-memory TTLCache (512 entries, 10 min) → hit: return
                                                    → miss ↓
                          PostgreSQL kanji_cache (30-day TTL) → hit: return
                                                               → miss ↓
                                              External API → store both levels
```

### Tasks

- [ ] `backend/app/services/cache.py`:
  ```python
  from cachetools import TTLCache
  _cache: TTLCache = TTLCache(maxsize=512, ttl=600)
  ```
- [ ] `get_kanji_cached(char)` / `set_kanji_cache(char, data)` — check/write both layers
- [ ] `KanjiCache` model: set `expires_at = NOW() + INTERVAL '30 days'`; filter expired rows on read
- [ ] Wrap kanji endpoint with cache decorator

### Done when
Second request for the same kanji character is served from in-memory cache (no DB/API call visible in logs).

---

## Phase 7 — External API Integrations

**Goal:** Live dictionary data and AI explanations work correctly.

### 7a — Jisho.org (Japanese dictionary)

- [ ] `backend/app/services/jisho.py`:
  - `async def search(query: str) -> list[DictEntry]` using `httpx.AsyncClient`
  - Parse `data[].senses[].english_definitions` and `japanese[].reading`
  - Handle `503` / timeout with `httpx.TimeoutException`

### 7b — CC-CEDICT (Chinese dictionary)

- [ ] Download `cedict_ts.u8` and load into memory at startup (lifespan event):
  ```python
  @asynccontextmanager
  async def lifespan(app):
      load_cedict()   # parse into dict[str, list[CedictEntry]]
      yield
  ```
- [ ] `search_cedict(query: str) -> list[DictEntry]` — O(1) lookup, no network call

### 7c — OpenRouter AI explanations (SSE)

- [ ] `routers/explain.py` — `POST /api/explain`
  - Accepts `list[TokenResult]`
  - Streams response from OpenRouter using Server-Sent Events
  - FastAPI `StreamingResponse` with `media_type="text/event-stream"`
  - Forward `Authorization: Bearer {OPENROUTER_API_KEY}` header (server-side, never exposed)

### Done when
`GET /api/search?q=猫&lang=jp` returns at least one result; `POST /api/explain` streams tokens to client.

---

## Phase 8 — Security Hardening

**Goal:** OWASP Top 10 mitigations in place before testing phase.

### Tasks

- [ ] **A01 — Broken Access Control:** `get_current_user` dependency on every protected route; vocabulary `DELETE` verifies `word.user_id == current_user.id`
- [ ] **A02 — Cryptographic Failures:** bcrypt cost 12, HTTPS enforced in production, `SECRET_KEY` min 32 chars validated at startup
- [ ] **A03 — Injection:** ORM parameterized queries everywhere (no raw SQL with user input); Pydantic validation on all request bodies
- [ ] **A05 — Security Misconfiguration:**
  ```python
  app.add_middleware(CORSMiddleware,
      allow_origins=settings.ALLOWED_ORIGINS,
      allow_credentials=True,
      allow_methods=["GET","POST","DELETE"],
  )
  ```
  Add security headers via middleware: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`
- [ ] **A06 — Vulnerable Components:** Add `dependabot.yml` for weekly pip updates
- [ ] **Rate limiting** via Redis:
  - Anonymous: 60 req/min
  - Authenticated: 120 req/min
  - Return `HTTP 429` with `Retry-After` header

  ```python
  async def rate_limit(request: Request, current_user=None):
      key = f"rl:{current_user.id if current_user else request.client.host}"
      limit = 120 if current_user else 60
      count = await redis.incr(key)
      if count == 1:
          await redis.expire(key, 60)
      if count > limit:
          raise HTTPException(429, headers={"Retry-After": "60"})
  ```

- [ ] **Input length caps** on `AnalyzeRequest.query` (max 500 chars), search `q` param (max 100 chars)

### Done when
CORS rejects unknown origins; rate limiter returns 429 after threshold; security headers present in every response.

---

## Phase 9 — Testing

**Goal:** 67% line coverage; all critical paths have integration tests.

### Test structure
```
backend/tests/
├── conftest.py           # async engine on SQLite, test client
├── test_classifier.py    # unit: all 4 QueryType branches
├── test_japanese.py      # unit: tokenizer output shape
├── test_chinese.py       # unit: pinyin, segmentation
├── test_auth.py          # integration: register, login, refresh, 401
├── test_analyze.py       # integration: 200, 206, 400 cases
├── test_vocabulary.py    # integration: CRUD, 403 on wrong user
└── test_kanji.py         # integration: cache hit/miss
```

### Key patterns

```python
# conftest.py
@pytest.fixture
async def client(tmp_path):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
```

- Use `httpx.AsyncClient` for all endpoint tests (no mocking of HTTP layer)
- Mock external APIs (`jisho`, `openrouter`) with `pytest-respx` or `respx`
- Coverage: `pytest --cov=app --cov-report=term-missing`; fail below 67%

### Done when
`pytest` passes; `--cov` report shows ≥ 67% line coverage.

---

## Phase 10 — Production Configuration

**Goal:** Deployment-ready compose file with secrets management and resource limits.

### Tasks

- [ ] Separate `docker-compose.prod.yml`:
  - `uvicorn --workers 4 --proxy-headers`
  - Postgres `max_connections=200`, `shared_buffers=256MB`
  - Redis `maxmemory 128mb`, `maxmemory-policy allkeys-lru`
  - All secrets from environment (no `.env` file in image)

- [ ] Health checks in compose:
  ```yaml
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
    interval: 30s
    timeout: 5s
    retries: 3
  ```

- [ ] Alembic migration step in `entrypoint.sh`:
  ```bash
  #!/bin/sh
  alembic upgrade head
  exec uvicorn app.main:app --host 0.0.0.0 --port 8000
  ```

- [ ] Structured JSON logging (uvicorn `--log-config` or `python-json-logger`)
- [ ] `README.md` with local setup instructions

### Done when
`docker compose -f docker-compose.prod.yml up` starts cleanly; `/health` returns 200; migrations applied automatically.

---

## Dependency & Version Reference

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | 0.111 | Web framework |
| `uvicorn[standard]` | 0.29 | ASGI server |
| `sqlalchemy[asyncio]` | 2.0 | ORM (async mode) |
| `asyncpg` | 0.29 | PostgreSQL async driver |
| `alembic` | 1.13 | Migrations |
| `pydantic-settings` | 2.2 | Config from env |
| `python-jose[cryptography]` | 3.3 | JWT |
| `passlib[bcrypt]` | 1.7 | Password hashing (cost 12) |
| `httpx` | 0.27 | Async HTTP client |
| `cachetools` | 5.3 | In-memory LRU/TTL cache |
| `redis` | 5.0 | Rate limiting |
| `sudachipy` | 0.6 | Japanese tokenizer |
| `sudachidict-core` | latest | UniDic dictionary |
| `hanlp` | 2.1 | Chinese NLP |
| `pypinyin` | 0.51 | Pinyin conversion |
| `pytest` | 8.2 | Test runner |
| `pytest-asyncio` | 0.23 | Async test support |

---

## Project File Structure

```
backend/
├── app/
│   ├── main.py                   # FastAPI app, lifespan, middleware registration
│   ├── core/
│   │   ├── config.py             # Settings (pydantic-settings)
│   │   └── security.py           # JWT helpers, bcrypt wrappers
│   ├── routers/
│   │   ├── auth.py               # /api/auth/*
│   │   ├── analyze.py            # POST /api/analyze
│   │   ├── search.py             # GET /api/search
│   │   ├── kanji.py              # GET /api/kanji/{char}
│   │   ├── explain.py            # POST /api/explain (SSE)
│   │   ├── vocabulary.py         # /api/vocabulary CRUD
│   │   └── history.py            # GET /api/history
│   ├── models/
│   │   ├── user.py
│   │   ├── saved_word.py
│   │   ├── search_history.py
│   │   └── kanji_cache.py
│   ├── schemas/
│   │   ├── auth.py               # UserCreate, UserResponse, TokenResponse
│   │   ├── analyze.py            # AnalyzeRequest, AnalyzeResponse, TokenResult
│   │   ├── kanji.py              # KanjiCard
│   │   ├── search.py             # DictEntry
│   │   └── vocabulary.py         # SavedWordCreate, SavedWord
│   ├── services/
│   │   ├── nlp/
│   │   │   ├── classifier.py
│   │   │   ├── japanese.py
│   │   │   └── chinese.py
│   │   ├── cache.py              # Two-level cache logic
│   │   ├── jisho.py              # Jisho API client
│   │   └── cedict.py             # CC-CEDICT loader + search
│   └── db/
│       ├── database.py           # Engine, session factory
│       └── alembic/              # Migrations
└── tests/
    ├── conftest.py
    ├── test_classifier.py
    ├── test_japanese.py
    ├── test_chinese.py
    ├── test_auth.py
    ├── test_analyze.py
    ├── test_vocabulary.py
    └── test_kanji.py
```

---

## API Surface Summary

| Method | URL | Auth | Status codes |
|--------|-----|------|--------------|
| `GET` | `/health` | No | 200 |
| `POST` | `/api/auth/register` | No | 201, 409 |
| `POST` | `/api/auth/login` | No | 200, 401 |
| `POST` | `/api/auth/refresh` | Cookie | 200, 401 |
| `POST` | `/api/analyze` | Yes | 200, 206, 400 |
| `GET` | `/api/search` | Yes | 200 |
| `GET` | `/api/kanji/{char}` | Yes | 200, 404 |
| `POST` | `/api/explain` | Yes | 200 (SSE) |
| `GET` | `/api/vocabulary` | Yes | 200 |
| `POST` | `/api/vocabulary` | Yes | 201, 409 |
| `DELETE` | `/api/vocabulary/{id}` | Yes | 204, 403, 404 |
| `GET` | `/api/history` | Yes | 200 |
