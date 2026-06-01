# AGENTS.md

Machine-facing guide for the JpDict backend. Human-oriented detail lives in [`README.md`](README.md) and [`docs/`](docs/README.md) — this file is the fast orientation; link out rather than duplicate.

## Project in one paragraph

Async **FastAPI** backend for a Japanese + Chinese language-learning app: tokenizes/annotates text (NLP), serves dictionary, kanji, and example-sentence lookups, and manages user accounts, saved vocabulary, and search history. Data lives in **PostgreSQL** (with `pg_trgm`); **Redis** + an in-memory TTL cache sit in front of hot paths. It is consumed by a separate **Next.js** frontend, which generates its types from the live OpenAPI schema.

## Setup & run

```bash
git lfs pull                 # dictionary source files in data/ are stored in Git LFS
uv sync --extra dev          # install runtime + dev deps (ruff, mypy, pytest)
cp .env.example .env         # then edit secrets as needed; never commit .env
make migrate                 # apply Alembic migrations (async)
make dev                     # start Postgres + Redis in Docker, run uvicorn --reload
make import-all              # populate dictionaries — REQUIRED before search returns results
```

API at `http://localhost:8000`; interactive docs at `/docs`.

## Test / lint / typecheck

| Command | What it does |
|---|---|
| `uv run pytest` (or `make test`) | Run the test suite |
| `make lint` | `ruff check app` + `ruff format --check app` — must pass before pushing |
| `make format` | Auto-fix lint findings and format in place |
| `make typecheck` | `mypy app` — advisory; a small known baseline of errors remains |

## Directory map

| Path | Role |
|---|---|
| `app/routers/` | One file per endpoint group; HTTP only, no business logic |
| `app/services/` | Business logic (dictionary search, NLP, caching) — the real work lives here |
| `app/models/` | SQLAlchemy ORM models |
| `app/schemas/` | Pydantic request/response schemas (the API edges) |
| `app/core/` | Config, security/JWT, rate limiting, dependencies |
| `app/db/` | Async engine + session factory |
| `scripts/` | One-off data importers (JMdict, KANJIDIC2, CC-CEDICT, ...) |
| `alembic/` | Async migrations |
| `tests/` | Pytest suite |

## Conventions

- **Async everywhere** — handlers, services, and DB access are `async`.
- **Session injection** — get the DB session via `Depends(get_session)`, never construct it.
- **No business logic in routers** — routers validate/parse and delegate to `app/services`.
- **Pydantic at the edges** — requests/responses are Pydantic schemas; services return models or typed dicts.
- Every public service function and router handler carries a one-line docstring (intent + return shape).

## Gotchas

- **Search is empty until data is imported.** Run `make import-all` (after `git lfs pull`) or lookups return nothing.
- **Migrations are async** (Alembic + asyncpg) — generated revisions must be reviewed before commit.
- **Never commit `.env`** — it is gitignored; secrets stay local.
- The canonical API contract is the **live OpenAPI** at `GET /openapi.json`; [`docs/API.md`](docs/API.md) is its prose companion.

## More

- Contributing workflow (branches, migrations, pre-push checks): [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Full docs index: [`docs/README.md`](docs/README.md)
