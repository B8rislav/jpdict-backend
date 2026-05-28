#!/usr/bin/env python3
"""
Import KRADFILE into kanjidic_entries.components[].

KRADFILE maps each kanji to the set of radical components it is built from.
Example lines (EUC-JP encoded):
    語 : 言 口 五
    漢 : 口 土 又 水

Must be run AFTER import_kanjidic2.py.

Usage:
    DATABASE_URL=postgresql://user:pass@host/db uv run python scripts/import_kradfile.py
    # or via make:
    make import-kradfile
"""
import asyncio
import gzip
import os
import sys
from pathlib import Path

import asyncpg

DATA_DIR = Path(__file__).parent.parent / "data"
KRADFILE_PATH = DATA_DIR / "kradfile.gz"

BATCH_SIZE = 500


def parse_kradfile(path: Path) -> dict[str, list[str]]:
    """
    Parse KRADFILE (EUC-JP) and return {kanji: [component, ...]} mapping.

    Comment lines start with '#'. Data lines have the form:
        <kanji> : <comp1> <comp2> ...
    where kanji and components are Unicode characters separated by spaces.
    """
    result: dict[str, list[str]] = {}
    with gzip.open(path) as raw:
        # KRADFILE is EUC-JP encoded
        for line in raw:
            decoded = line.decode("euc-jp", errors="replace").strip()
            if not decoded or decoded.startswith("#"):
                continue
            if " : " not in decoded:
                continue
            kanji_part, components_part = decoded.split(" : ", 1)
            kanji = kanji_part.strip()
            components = [c for c in components_part.split() if c]
            if kanji and components:
                result[kanji] = components
    return result


async def main() -> None:
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        sys.exit("ERROR: DATABASE_URL not set")
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    if not KRADFILE_PATH.exists():
        sys.exit(f"ERROR: {KRADFILE_PATH} not found — place kradfile.gz in the data/ directory")

    conn = await asyncpg.connect(db_url)
    try:
        # Check if kanjidic_entries is populated
        count = await conn.fetchval("SELECT COUNT(*) FROM kanjidic_entries")
        if count == 0:
            sys.exit("ERROR: kanjidic_entries is empty — run import_kanjidic2.py first")

        # Check if components are already populated
        filled = await conn.fetchval(
            "SELECT COUNT(*) FROM kanjidic_entries WHERE array_length(components, 1) > 0"
        )
        if filled > 0:
            print(f"  components already populated on {filled:,} rows — skipping")
            return

        print("  parsing KRADFILE ...")
        krad = parse_kradfile(KRADFILE_PATH)
        print(f"  parsed {len(krad):,} kanji decompositions")

        # Bulk update in batches
        items = list(krad.items())
        total = 0
        for i in range(0, len(items), BATCH_SIZE):
            batch = items[i : i + BATCH_SIZE]
            await conn.executemany(
                "UPDATE kanjidic_entries SET components = $2 WHERE character = $1",
                [(kanji, components) for kanji, components in batch],
            )
            total += len(batch)
            print(f"  updated {total:,} ...", end="\r")

        updated = await conn.fetchval(
            "SELECT COUNT(*) FROM kanjidic_entries WHERE array_length(components, 1) > 0"
        )
        print(f"  done — {updated:,} kanji now have component decomposition")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
