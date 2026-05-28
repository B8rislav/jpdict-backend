#!/usr/bin/env python3
"""
Derive Russian kanji meanings from existing JMdict data.

For each kanji in kanjidic_entries, finds the most relevant JMdict entry
(preferring entries where the kanji is the primary single-character headword)
and extracts Russian glosses into kanjidic_entries.meanings_ru.  Idempotent —
re-running replaces existing values.

Requires: import_jmdict.py must have run first.

Usage:
    DATABASE_URL=postgresql://user:pass@host/db uv run python scripts/import_kanji_ru.py
    # or via make:
    make import-kanji-ru
"""
import asyncio
import json
import os
import sys

import asyncpg

BATCH_SIZE = 200
MAX_GLOSSES = 5


async def main() -> None:
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        sys.exit("ERROR: DATABASE_URL not set")
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    conn = await asyncpg.connect(db_url)
    try:
        print("  deriving Russian kanji meanings from JMdict ...")

        # For each kanji pick the best-matching JMdict entry:
        #   rank 0 — entry whose sole kanji_form IS this character (e.g. 猫→ねこ)
        #   rank 1 — entry whose first kanji_form is this character (compound ok)
        #   rank 2 — any entry that contains the character as a kanji_form
        # Within each rank, prefer common words, then lower JLPT number (=easier).
        rows = await conn.fetch(
            """
            WITH ranked AS (
                SELECT
                    k.character,
                    e.senses,
                    row_number() OVER (
                        PARTITION BY k.character
                        ORDER BY
                            CASE
                                WHEN e.kanji_forms[1] = k.character
                                     AND array_length(e.kanji_forms, 1) = 1 THEN 0
                                WHEN e.kanji_forms[1] = k.character THEN 1
                                ELSE 2
                            END,
                            e.common DESC NULLS LAST,
                            e.jlpt_level ASC NULLS LAST
                    ) AS rn
                FROM kanjidic_entries k
                JOIN jmdict_entries e ON k.character = ANY(e.kanji_forms)
            )
            SELECT character, senses
            FROM ranked
            WHERE rn = 1
            """
        )

        batch: list[tuple[list[str], str]] = []
        total = 0

        for row in rows:
            raw = row["senses"]
            # asyncpg returns JSONB as a raw string; SQLAlchemy would auto-decode
            if isinstance(raw, str):
                senses: list = json.loads(raw)
            else:
                senses = raw or []

            ru_meanings: list[str] = []
            for sense in senses:
                if isinstance(sense, str):
                    sense = json.loads(sense)
                ru_meanings.extend(sense.get("ru") or [])

            if not ru_meanings:
                continue

            batch.append((ru_meanings[:MAX_GLOSSES], row["character"]))

            if len(batch) >= BATCH_SIZE:
                await conn.executemany(
                    "UPDATE kanjidic_entries SET meanings_ru = $1 WHERE character = $2",
                    batch,
                )
                total += len(batch)
                batch = []
                print(f"  updated {total:,} ...", end="\r")

        if batch:
            await conn.executemany(
                "UPDATE kanjidic_entries SET meanings_ru = $1 WHERE character = $2",
                batch,
            )
            total += len(batch)

        covered = await conn.fetchval(
            "SELECT COUNT(*) FROM kanjidic_entries "
            "WHERE array_length(meanings_ru, 1) > 0"
        )
        total_kanji = await conn.fetchval("SELECT COUNT(*) FROM kanjidic_entries")
        print(
            f"\n  done — {covered:,}/{total_kanji:,} kanji have Russian meanings "
            f"({100 * covered // total_kanji}%)"
        )
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
