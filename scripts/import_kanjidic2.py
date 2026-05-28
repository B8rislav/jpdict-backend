#!/usr/bin/env python3
"""
Import KANJIDIC2 into kanjidic_entries.

Reads kanjidic2.xml.gz from the data/ directory and inserts ~13,000 kanji
records with stroke count, JLPT level, grade, readings, and meanings.
Run import_kradfile.py afterwards to populate the components[] column.

Usage:
    DATABASE_URL=postgresql://user:pass@host/db uv run python scripts/import_kanjidic2.py
    # or via make:
    make import-kanjidic
"""
import asyncio
import gzip
import os
import sys
from pathlib import Path

import asyncpg
from lxml import etree

DATA_DIR = Path(__file__).parent.parent / "data"
KANJIDIC_PATH = DATA_DIR / "kanjidic2.xml.gz"

BATCH_SIZE = 200


def parse_kanjidic2(path: Path):
    """
    Yield dicts for each KANJIDIC2 <character> element.

    JLPT levels in kanjidic2 are stored in <misc><jlpt> as integers 1-4
    in the old 4-level system. Mapping:
        old 4 → N5
        old 3 → N4
        old 2 → N3/N2 (ambiguous; stored as-is then remapped below)
        old 1 → N2/N1 (same issue)
    The new 5-level JLPT kanji list is community-maintained; this gives a
    reasonable approximation. For a fully accurate N1-N5 mapping run
    import_kradfile.py or a supplementary JLPT kanji script.

    Old→New rough mapping used here:
        4 → 5 (N5, easiest)
        3 → 4 (N4)
        2 → 3 (N3, middle ground)
        1 → 2 (N2)
    Note: N1-only kanji are not present in kanjidic2's <jlpt> field.
    """
    OLD_TO_NEW = {4: 5, 3: 4, 2: 3, 1: 2}

    with gzip.open(path) as f:
        context = etree.iterparse(f, events=("end",), no_network=True)
        for _, elem in context:
            if elem.tag != "character":
                continue

            character = elem.findtext("literal")
            if not character:
                elem.clear()
                continue

            # Stroke count (first value; may have stroke-count variants)
            stroke_count = None
            sc_elem = elem.find("misc/stroke_count")
            if sc_elem is not None and sc_elem.text:
                try:
                    stroke_count = int(sc_elem.text)
                except ValueError:
                    pass

            # JLPT level (old 4-level; converted above)
            jlpt_old = None
            jlpt_elem = elem.find("misc/jlpt")
            if jlpt_elem is not None and jlpt_elem.text:
                try:
                    jlpt_old = int(jlpt_elem.text)
                except ValueError:
                    pass
            jlpt_level = OLD_TO_NEW.get(jlpt_old) if jlpt_old is not None else None

            # School grade (1-6 = elementary, 8 = Joyo secondary)
            grade = None
            grade_elem = elem.find("misc/grade")
            if grade_elem is not None and grade_elem.text:
                try:
                    grade = int(grade_elem.text)
                except ValueError:
                    pass

            # Joyo frequency rank (1-2500, lower = more frequent)
            frequency = None
            freq_elem = elem.find("misc/freq")
            if freq_elem is not None and freq_elem.text:
                try:
                    frequency = int(freq_elem.text)
                except ValueError:
                    pass

            # Classical/Nelson radical number
            radical_number = None
            for rad in elem.findall("radical/rad_value"):
                if rad.get("rad_type") == "classical":
                    try:
                        radical_number = int(rad.text)
                    except (ValueError, TypeError):
                        pass
                    break

            # On-readings (音読み)
            on_readings = [
                r.text for r in elem.findall("reading_meaning/rmgroup/reading")
                if r.get("r_type") == "ja_on" and r.text
            ]

            # Kun-readings (訓読み)
            kun_readings = [
                r.text for r in elem.findall("reading_meaning/rmgroup/reading")
                if r.get("r_type") == "ja_kun" and r.text
            ]

            # English meanings
            meanings_en = [
                m.text for m in elem.findall("reading_meaning/rmgroup/meaning")
                if m.get("m_lang") is None and m.text  # no m_lang attr = English
            ]

            elem.clear()
            yield {
                "character": character,
                "stroke_count": stroke_count,
                "jlpt_level": jlpt_level,
                "grade": grade,
                "frequency": frequency,
                "on_readings": on_readings,
                "kun_readings": kun_readings,
                "meanings_en": meanings_en,
                "radical_number": radical_number,
            }


async def insert_batch(conn: asyncpg.Connection, batch: list[dict]) -> None:
    await conn.executemany(
        """
        INSERT INTO kanjidic_entries
            (character, stroke_count, jlpt_level, grade, frequency,
             on_readings, kun_readings, meanings_en, radical_number)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        ON CONFLICT (character) DO UPDATE SET
            stroke_count   = EXCLUDED.stroke_count,
            jlpt_level     = EXCLUDED.jlpt_level,
            grade          = EXCLUDED.grade,
            frequency      = EXCLUDED.frequency,
            on_readings    = EXCLUDED.on_readings,
            kun_readings   = EXCLUDED.kun_readings,
            meanings_en    = EXCLUDED.meanings_en,
            radical_number = EXCLUDED.radical_number
        """,
        [
            (
                e["character"],
                e["stroke_count"],
                e["jlpt_level"],
                e["grade"],
                e["frequency"],
                e["on_readings"],
                e["kun_readings"],
                e["meanings_en"],
                e["radical_number"],
            )
            for e in batch
        ],
    )


async def main() -> None:
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        sys.exit("ERROR: DATABASE_URL not set")
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    if not KANJIDIC_PATH.exists():
        sys.exit(f"ERROR: {KANJIDIC_PATH} not found — place kanjidic2.xml.gz in the data/ directory")

    conn = await asyncpg.connect(db_url)
    try:
        count = await conn.fetchval("SELECT COUNT(*) FROM kanjidic_entries")
        if count > 0:
            print(f"  kanjidic_entries already has {count:,} rows — skipping")
            return

        print("  parsing KANJIDIC2 XML ...")
        batch: list[dict] = []
        total = 0
        for entry in parse_kanjidic2(KANJIDIC_PATH):
            batch.append(entry)
            if len(batch) >= BATCH_SIZE:
                await insert_batch(conn, batch)
                total += len(batch)
                batch = []
                print(f"  inserted {total:,} ...", end="\r")
        if batch:
            await insert_batch(conn, batch)
            total += len(batch)

        final = await conn.fetchval("SELECT COUNT(*) FROM kanjidic_entries")
        print(f"  done — {final:,} kanji in kanjidic_entries")
        print("  tip: run import_kradfile.py to populate component decomposition")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
