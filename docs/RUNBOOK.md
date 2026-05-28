# Runbook

Operational recipes for common tasks.

---

## Rebuild the local database from scratch

Destroys all data and runs migrations fresh.

```bash
# Stop everything and remove volumes
docker compose down -v

# Bring DB and cache back up
docker compose up db cache -d

# Apply all migrations
make migrate

# Re-import all dictionary data (takes 5–15 min)
make import-all
```

If you only want to reset one specific table, drop and recreate it with Alembic by targeting a specific revision:

```bash
# Downgrade to before a specific migration
uv run --env-file .env alembic downgrade <revision>

# Then re-apply
uv run --env-file .env alembic upgrade head
```

---

## Re-run a single import script

All import scripts are idempotent: they skip rows that already exist. To force a fresh import, truncate the table first.

```bash
# Example: re-import Tatoeba sentences
psql "$DATABASE_URL" -c "TRUNCATE TABLE reibun_entries RESTART IDENTITY;"
make import-reibun
```

Available make targets and what they populate:

| Target | Script | Table |
|---|---|---|
| `make import-jmdict` | `scripts/import_jmdict.py` | `jmdict_entries` |
| `make import-kanjidic` | `scripts/import_kanjidic2.py` | `kanjidic_entries` |
| `make import-kradfile` | `scripts/import_kradfile.py` | `kanjidic_entries.components` |
| `make import-cedict` | `scripts/import_cedict.py` | `cedict_entries` |
| `make import-hsk` | `scripts/import_hsk.py` | `cedict_entries.hsk_level + definitions.ru` |
| `make import-kanji-ru` | `scripts/import_kanji_ru.py` | `kanjidic_entries.meanings_ru` |
| `make import-reibun` | `scripts/import_tatoeba.py` | `reibun_entries` |
| `make import-all` | all of the above | all tables (correct order) |

---

## Rotate `SECRET_KEY`

Changing `SECRET_KEY` immediately invalidates **all existing access and refresh tokens**. All logged-in users will be signed out.

```bash
# Generate a new 64-character secret
python -c "import secrets; print(secrets.token_hex(32))"

# Update .env
# SECRET_KEY=<new value>

# Restart the API process to pick up the new key
# (docker compose: restart the backend service)
docker compose restart backend
```

In production, update the secret in your secrets manager and trigger a rolling restart of all API workers. There is no need to migrate the database — the key is only used for JWT signing.

---

## Drain the kanji cache

The kanji cache has two levels: in-memory (`TTLCache`) and the `kanji_cache` Postgres table.

The in-memory cache drains automatically when the process restarts (TTL 10 min).

To clear the Postgres cache immediately:

```bash
psql "$DATABASE_URL" -c "TRUNCATE TABLE kanji_cache;"
```

To clear only expired entries (safe to run without downtime):

```bash
psql "$DATABASE_URL" -c "DELETE FROM kanji_cache WHERE expires_at < NOW();"
```

---

## Inspect rate-limiter state in Redis

```bash
# Connect to the Redis container
docker compose exec cache redis-cli

# Count all rate-limit keys
KEYS rl:*

# Check remaining requests for a specific IP
GET rl:ip:127.0.0.1
TTL rl:ip:127.0.0.1

# Check remaining requests for a user (UUID)
GET rl:user:<uuid>
TTL rl:user:<uuid>

# Reset the limit for a specific key
DEL rl:ip:127.0.0.1
```

Keys expire automatically after 60 seconds (the window size). No manual cleanup is needed.

---

## Tail JSON logs

The API outputs structured JSON logs configured via `log_config.json`.

```bash
# When running locally with make dev
uv run --env-file .env uvicorn app.main:app --reload --log-config log_config.json

# When running in Docker
docker compose logs -f backend

# Pretty-print with jq (filter to ERROR and above)
docker compose logs -f backend | jq 'select(.level == "ERROR" or .level == "CRITICAL")'

# Filter to a specific request path
docker compose logs -f backend | jq 'select(.message | contains("/api/search"))'

# Show the last 100 lines
docker compose logs --tail=100 backend
```

Log fields: `timestamp`, `level`, `logger`, `message`, plus `exc_info` on exceptions.

---

## Run the test suite

```bash
# All tests
uv run pytest

# With coverage
uv run pytest --cov=app --cov-report=term-missing

# Single test file
uv run pytest tests/test_auth.py -v

# Stop on first failure
uv run pytest -x
```

Tests use an in-memory or test database; see `tests/conftest.py` for the fixture setup.
