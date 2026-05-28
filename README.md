# JpDict Backend

REST API for a Japanese and Chinese language learning web application. Handles text analysis, dictionary search, vocabulary management, and AI-powered explanations.

## Documentation

Full reference docs live in [`docs/`](docs/README.md).

| Doc | What it covers |
|---|---|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Component diagram and request lifecycle |
| [STRUCTURE.md](docs/STRUCTURE.md) | Every file in the repo with its role |
| [RUNBOOK.md](docs/RUNBOOK.md) | Rebuild DB, rotate keys, drain cache, tail logs |
| [API.md](docs/API.md) | All endpoints with schemas and line numbers |
| [DATABASE.md](docs/DATABASE.md) | Tables, columns, indexes, FK relations |
| [NLP.md](docs/NLP.md) | SudachiPy / jieba pipeline and caveats |
| [SECURITY.md](docs/SECURITY.md) | Auth, rate limiting, headers, threat model |
| [DATA_SOURCES.md](docs/DATA_SOURCES.md) | Corpus licenses and import instructions |

## Tech stack

| Layer | Technology |
|---|---|
| Framework | FastAPI 0.111 + Uvicorn (ASGI) |
| Database | PostgreSQL 15 with `pg_trgm`, `pgvector` |
| ORM / migrations | SQLAlchemy 2.0 async + Alembic |
| Auth | JWT (python-jose) + bcrypt (passlib) |
| Cache | In-memory TTLCache + Redis 7 |
| NLP — Japanese | SudachiPy + SudachiDict-core |
| NLP — Chinese | HanLP + pypinyin |
| HTTP client | httpx (async) |
| AI explanations | OpenRouter API (SSE streaming) |

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Docker + Docker Compose

## Local setup

```bash
# 1. Install dependencies
uv sync --extra dev

# 2. Copy and fill in environment variables
cp .env.example .env

# 3. Run migrations
make migrate

# 4. Start the API server (also starts DB and Redis in Docker)
make dev
```

API is available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

| Command | Description |
|---|---|
| `make dev` | Start DB + Redis in Docker, run API locally with hot reload |
| `make migrate` | Run pending Alembic migrations |
| `make logs` | Tail DB and Redis logs |
| `make stop` | Stop Docker containers |
| `make build` | Build and run everything in Docker |

## Running with Docker (development)

```bash
docker compose up --build
```

Starts `db`, `cache`, and `backend`. Migrations run automatically on container start.

## Running in production

```bash
# Required — set all variables in your shell or a secrets manager before starting
export POSTGRES_DB=jpdict
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=<strong-password>
export DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
export REDIS_URL=redis://cache:6379/0
export SECRET_KEY=<random-string-at-least-32-chars>
export OPENROUTER_API_KEY=<your-key>
export ALLOWED_ORIGINS=https://your-frontend-domain.com
# Frontend
export NEXT_PUBLIC_BACKEND_URL=https://api.your-domain.com
export NEXT_PUBLIC_API_KEY=<optional-public-key>
export OPENROUTER_KEY=<same-openrouter-key>
export JWT_SECRET=<same-as-SECRET_KEY-or-separate>

docker compose -f docker-compose.prod.yml up --build -d
```

On first boot the container runs migrations and all dictionary imports automatically, then starts uvicorn with 4 workers. Subsequent starts skip the imports (tables already populated).

## Importing dictionary data manually

The import scripts are also available as Makefile targets and run idempotently (no-op when the target table already has rows):

```bash
make import-jmdict    # JMdict — Japanese words + JLPT levels
make import-kanjidic  # KANJIDIC2 — kanji stroke count, readings, grade
make import-kradfile  # KRADFILE — kanji component decomposition (run after kanjidic)
make import-cedict    # CC-CEDICT — Chinese-English dictionary
make import-hsk       # HSK 1-6 levels (run after cedict)
make import-all       # All of the above in the correct order
```

## Environment variables

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string, e.g. `postgresql+asyncpg://postgres:postgres@localhost:5432/jpdict` |
| `REDIS_URL` | Redis connection string, e.g. `redis://localhost:6379` |
| `SECRET_KEY` | JWT signing secret, minimum 32 characters |
| `OPENROUTER_API_KEY` | API key for OpenRouter (AI explanations) |
| `ALLOWED_ORIGINS` | Comma-separated list of allowed CORS origins |

## Running tests

```bash
uv run pytest
```

With coverage report:

```bash
uv run pytest --cov=app --cov-report=term-missing
```

## API overview

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/health` | No | Health check |
| POST | `/api/auth/register` | No | Create account |
| POST | `/api/auth/login` | No | Login, returns JWT + refresh cookie |
| POST | `/api/auth/refresh` | Cookie | Refresh access token |
| POST | `/api/analyze` | No | Tokenize and annotate Japanese or Chinese text |
| GET | `/api/search` | No | Dictionary search |
| GET | `/api/kanji/{char}` | No | Kanji detail card |
| POST | `/api/explain` | Yes | AI explanation (SSE stream) |
| GET | `/api/vocabulary` | Yes | List saved words |
| POST | `/api/vocabulary` | Yes | Save a word |
| DELETE | `/api/vocabulary/{id}` | Yes | Delete a saved word |
| GET | `/api/history` | Yes | Search history |

## Project structure

```
app/
├── main.py              # FastAPI entry point, lifespan, middleware
├── core/
│   ├── config.py        # Settings loaded from environment
│   └── security.py      # JWT helpers, bcrypt wrappers
├── routers/             # One file per endpoint group
├── models/              # SQLAlchemy ORM models
├── schemas/             # Pydantic request/response schemas
├── services/
│   ├── nlp/             # classifier.py, japanese.py, chinese.py
│   └── cache.py         # Two-level cache (TTLCache + PostgreSQL)
└── db/
    └── database.py      # Async engine and session factory
alembic/
└── versions/            # Migration files
scripts/                 # One-off data import scripts (JMdict, CC-CEDICT)
tests/
```

## Dictionary data

Japanese and Chinese dictionary data is loaded into PostgreSQL from open datasets rather than called from external APIs at runtime:

- **Japanese:** JMdict (words) + KANJIDIC2 (kanji details) — run `python scripts/import_jmdict.py`
- **Chinese:** CC-CEDICT + HSK wordlists — run `python scripts/import_cedict.py`

Import scripts are idempotent and run automatically on first container start if the tables are empty.
