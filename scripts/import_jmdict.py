#!/usr/bin/env python3
"""
Import JMdict into jmdict_entries.

Reads JMdict.gz from the data/ directory and bulk-inserts into PostgreSQL.
Idempotent: skips if table already has rows.

Usage:
    DATABASE_URL=postgresql://user:pass@host/db uv run python scripts/import_jmdict.py
    # or via make:
    make import-jmdict
"""
import asyncio
import gzip
import json
import os
import sys
from pathlib import Path

import asyncpg
from lxml import etree

DATA_DIR = Path(__file__).parent.parent / "data"
JMDICT_PATH = DATA_DIR / "JMdict.gz"

XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"

# <misc> entity values that encode JLPT level
JLPT_MISC = {
    "jlpt-n1": 1,
    "jlpt-n2": 2,
    "jlpt-n3": 3,
    "jlpt-n4": 4,
    "jlpt-n5": 5,
}

# Common-word priority prefixes used by EDRDG
COMMON_PRIOS = ("ichi1", "news1", "spec1", "gai1")

BATCH_SIZE = 500


def _is_common(elem: etree._Element) -> bool:
    for ke in elem.findall("k_ele"):
        if any(p.text and p.text.startswith(COMMON_PRIOS) for p in ke.findall("ke_pri")):
            return True
    for re in elem.findall("r_ele"):
        if any(p.text and p.text.startswith(COMMON_PRIOS) for p in re.findall("re_pri")):
            return True
    return False


def parse_jmdict(path: Path):
    """
    Yield dicts for each JMdict entry.

    lxml load_dtd=True resolves the embedded entity definitions so that
    <pos>&n;</pos> becomes the full resolved string and
    <misc>&jlpt-n1;</misc> becomes "jlpt-n1".
    """
    with gzip.open(path) as f:
        context = etree.iterparse(
            f, events=("end",), load_dtd=True, resolve_entities=True, no_network=True
        )
        for _, elem in context:
            if elem.tag != "entry":
                continue

            entry_id = int(elem.findtext("ent_seq"))
            kanji_forms = [ke.findtext("keb") for ke in elem.findall("k_ele") if ke.findtext("keb")]
            reading_forms = [re.findtext("reb") for re in elem.findall("r_ele") if re.findtext("reb")]
            common = _is_common(elem)

            senses = []
            jlpt_level = None
            last_pos: list[str] = []

            for sense_elem in elem.findall("sense"):
                pos_elems = sense_elem.findall("pos")
                if pos_elems:
                    last_pos = [p.text for p in pos_elems if p.text]

                misc_texts = [m.text for m in sense_elem.findall("misc") if m.text]
                for m in misc_texts:
                    # JLPT level is stored in the first sense that mentions it
                    if m in JLPT_MISC and jlpt_level is None:
                        jlpt_level = JLPT_MISC[m]

                gloss_en = [
                    g.text for g in sense_elem.findall("gloss")
                    if g.text and g.get(XML_LANG, "eng") == "eng"
                ]
                gloss_ru = [
                    g.text for g in sense_elem.findall("gloss")
                    if g.text and g.get(XML_LANG) == "rus"
                ]
                field = [fi.text for fi in sense_elem.findall("field") if fi.text]

                # Only include senses that have at least one gloss
                if gloss_en or gloss_ru:
                    senses.append({
                        "pos": list(last_pos),
                        "en": gloss_en,
                        "ru": gloss_ru,
                        "misc": [m for m in misc_texts if m not in JLPT_MISC],
                        "field": field,
                    })

            elem.clear()
            yield {
                "entry_id": entry_id,
                "kanji_forms": kanji_forms,
                "reading_forms": reading_forms,
                "senses": senses,
                "jlpt_level": jlpt_level,
                "common": common,
            }


def _flat_glosses(senses: list[dict], lang: str) -> str | None:
    parts = [g for s in senses for g in (s.get(lang) or [])]
    return "\n".join(parts) if parts else None


async def insert_batch(conn: asyncpg.Connection, batch: list[dict]) -> None:
    await conn.executemany(
        """
        INSERT INTO jmdict_entries
            (entry_id, kanji_forms, reading_forms, senses, jlpt_level, common,
             senses_glosses_en, senses_glosses_ru)
        VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7, $8)
        ON CONFLICT (entry_id) DO NOTHING
        """,
        [
            (
                e["entry_id"],
                e["kanji_forms"],
                e["reading_forms"],
                json.dumps(e["senses"], ensure_ascii=False),
                e["jlpt_level"],
                e["common"],
                _flat_glosses(e["senses"], "en"),
                _flat_glosses(e["senses"], "ru"),
            )
            for e in batch
        ],
    )


async def main() -> None:
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        sys.exit("ERROR: DATABASE_URL not set")
    # asyncpg expects postgresql:// not postgresql+asyncpg://
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    if not JMDICT_PATH.exists():
        sys.exit(f"ERROR: {JMDICT_PATH} not found — place JMdict.gz in the data/ directory")

    conn = await asyncpg.connect(db_url)
    try:
        count = await conn.fetchval("SELECT COUNT(*) FROM jmdict_entries")
        if count > 0:
            print(f"  jmdict_entries already has {count:,} rows — skipping")
            return

        print("  parsing JMdict XML ...")
        batch: list[dict] = []
        total = 0
        for entry in parse_jmdict(JMDICT_PATH):
            batch.append(entry)
            if len(batch) >= BATCH_SIZE:
                await insert_batch(conn, batch)
                total += len(batch)
                batch = []
                print(f"  inserted {total:,} ...", end="\r")
        if batch:
            await insert_batch(conn, batch)
            total += len(batch)

        final = await conn.fetchval("SELECT COUNT(*) FROM jmdict_entries")
        print(f"  done — {final:,} entries in jmdict_entries")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
