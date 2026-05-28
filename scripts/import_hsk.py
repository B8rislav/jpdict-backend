#!/usr/bin/env python3
"""
Populate hsk_level and Russian definitions on cedict_entries.

Reads hsk.json from the data/ directory (LiudmilaLV/json_hsk, MIT licence)
which contains all 5,000 HSK 1-6 words with English and Russian translations.

For each entry matching cedict_entries.simplified:
  - sets hsk_level
  - sets definitions->>'ru' from the HSK Russian translations

Safe to re-run.

Usage:
    DATABASE_URL=postgresql://user:pass@host/db uv run python scripts/import_hsk.py
    # or via make:
    make import-hsk
"""
import asyncio
import json
import os
import sys
from pathlib import Path

import asyncpg

DATA_DIR = Path(__file__).parent.parent / "data"
HSK_PATH = DATA_DIR / "hsk.json"

BATCH_SIZE = 500


def load_hsk(path: Path) -> list[dict]:
    """
    Return list of {hanzi, level, ru} from hsk.json.

    hsk.json format: [{"hanzi": "爱", "level": 1,
                        "translations": {"eng": [...], "rus": [...]}}, ...]
    """
    entries = json.loads(path.read_text(encoding="utf-8"))
    result = []
    for e in entries:
        hanzi = e.get("hanzi", "").strip()
        level = e.get("level")
        if not hanzi or not isinstance(level, int):
            continue
        rus = e.get("translations", {}).get("rus") or []
        result.append({"hanzi": hanzi, "level": level, "ru": rus})
    return result


async def update_batch(conn: asyncpg.Connection, batch: list[dict]) -> None:
    """Set hsk_level and definitions->'ru' for each entry."""
    await conn.executemany(
        """
        UPDATE cedict_entries
           SET hsk_level  = $1,
               definitions = jsonb_set(definitions, '{ru}', $2::jsonb)
         WHERE simplified = $3
        """,
        [
            (e["level"], json.dumps(e["ru"], ensure_ascii=False), e["hanzi"])
            for e in batch
        ],
    )


async def main() -> None:
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        sys.exit("ERROR: DATABASE_URL not set")
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    if not HSK_PATH.exists():
        sys.exit(f"ERROR: {HSK_PATH} not found — place hsk.json in the data/ directory")

    entries = load_hsk(HSK_PATH)
    if not entries:
        sys.exit("ERROR: HSK data file is empty or unrecognised format")
    print(f"  loaded {len(entries):,} HSK entries (levels 1-6)")

    conn = await asyncpg.connect(db_url)
    try:
        cedict_count = await conn.fetchval("SELECT COUNT(*) FROM cedict_entries")
        if cedict_count == 0:
            sys.exit("ERROR: cedict_entries is empty — run import_cedict.py first")

        for i in range(0, len(entries), BATCH_SIZE):
            chunk = entries[i : i + BATCH_SIZE]
            await update_batch(conn, chunk)
            print(f"  processed {min(i + BATCH_SIZE, len(entries)):,} / {len(entries):,} ...", end="\r")

        total_updated = await conn.fetchval(
            "SELECT COUNT(*) FROM cedict_entries WHERE hsk_level IS NOT NULL"
        )
        print(f"  done — {total_updated:,} cedict_entries rows have hsk_level + definitions.ru")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
