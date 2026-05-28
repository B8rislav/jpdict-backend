#!/bin/sh
set -e

uv run alembic upgrade head

uv run python scripts/import_jmdict.py
uv run python scripts/import_kanjidic2.py
uv run python scripts/import_kradfile.py
uv run python scripts/import_cedict.py
uv run python scripts/import_hsk.py

exec uv run uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --proxy-headers \
  --log-config log_config.json
