#!/usr/bin/env python3
"""
Import CC-CEDICT into cedict_entries (English definitions).

Reads cedict_ts.u8.gz from the data/ directory, parses line-by-line with
regex, and bulk-inserts into PostgreSQL. Idempotent: skips if table already
has rows.

CC-CEDICT line format:
    Traditional Simplified [pin1 yin1] /definition 1/definition 2/.../

Usage:
    DATABASE_URL=postgresql://user:pass@host/db uv run python scripts/import_cedict.py
    # or via make:
    make import-cedict
"""
import asyncio
import gzip
import json
import os
import re
import sys
from pathlib import Path

import asyncpg

DATA_DIR = Path(__file__).parent.parent / "data"
CEDICT_PATH = DATA_DIR / "cedict_ts.u8.gz"

# Traditional  Simplified  [pinyin]  /def1/def2/.../
_LINE_RE = re.compile(r"^(\S+)\s+(\S+)\s+\[([^\]]+)\]\s+/(.+)/\s*$")

BATCH_SIZE = 1000


def parse_cedict(path: Path):
    """Yield dicts for each CC-CEDICT entry, skipping comment lines."""
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = _LINE_RE.match(line)
            if not m:
                continue
            traditional, simplified, pinyin, raw_defs = m.groups()
            en = [d.strip() for d in raw_defs.split("/") if d.strip()]
            yield {
                "traditional": traditional,
                "simplified": simplified,
                "pinyin": pinyin,
                "definitions": {"en": en, "ru": []},
            }


def _flat_defs(definitions: dict, lang: str) -> str | None:
    parts = definitions.get(lang) or []
    return "\n".join(parts) if parts else None


async def insert_batch(conn: asyncpg.Connection, batch: list[dict]) -> None:
    await conn.executemany(
        """
        INSERT INTO cedict_entries
            (traditional, simplified, pinyin, definitions,
             definitions_flat_en, definitions_flat_ru)
        VALUES ($1, $2, $3, $4::jsonb, $5, $6)
        """,
        [
            (
                e["traditional"],
                e["simplified"],
                e["pinyin"],
                json.dumps(e["definitions"], ensure_ascii=False),
                _flat_defs(e["definitions"], "en"),
                _flat_defs(e["definitions"], "ru"),
            )
            for e in batch
        ],
    )


async def main() -> None:
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        sys.exit("ERROR: DATABASE_URL not set")
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    if not CEDICT_PATH.exists():
        sys.exit(f"ERROR: {CEDICT_PATH} not found — place cedict_ts.u8.gz in the data/ directory")

    conn = await asyncpg.connect(db_url)
    try:
        count = await conn.fetchval("SELECT COUNT(*) FROM cedict_entries")
        if count > 0:
            print(f"  cedict_entries already has {count:,} rows — skipping")
            return

        print("  parsing CC-CEDICT ...")
        batch: list[dict] = []
        total = 0
        for entry in parse_cedict(CEDICT_PATH):
            batch.append(entry)
            if len(batch) >= BATCH_SIZE:
                await insert_batch(conn, batch)
                total += len(batch)
                batch = []
                print(f"  inserted {total:,} ...", end="\r")
        if batch:
            await insert_batch(conn, batch)
            total += len(batch)

        final = await conn.fetchval("SELECT COUNT(*) FROM cedict_entries")
        print(f"  done — {final:,} entries in cedict_entries")
        print("  tip: run import_hsk.py to populate hsk_level column")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
