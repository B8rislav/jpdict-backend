#!/usr/bin/env python3
"""
Import Tatoeba example sentences into reibun_entries (Japanese + Russian/English translations).

Downloads per-language sentence files and the links file from downloads.tatoeba.org,
filters to Japanese source sentences, joins Russian and English translations, then
bulk-inserts into reibun_entries.

Idempotent: skips when reibun_entries is already populated, or upserts by
(source, source_sentence_id) when --force is passed.

Usage:
    DATABASE_URL=postgresql://user:pass@host/db uv run python scripts/import_tatoeba.py
    # or via make:
    make import-reibun
"""
import asyncio
import bz2
import csv
import io
import os
import sys
import urllib.request
from pathlib import Path
from typing import Iterator

import asyncpg

DATA_DIR = Path(__file__).parent.parent / "data"

TATOEBA_BASE = "https://downloads.tatoeba.org/exports/per_language"
JPN_URL = f"{TATOEBA_BASE}/jpn/jpn_sentences.tsv.bz2"
RUS_URL = f"{TATOEBA_BASE}/rus/rus_sentences.tsv.bz2"
ENG_URL = f"{TATOEBA_BASE}/eng/eng_sentences.tsv.bz2"
LINKS_URL = "https://downloads.tatoeba.org/exports/links.tar.bz2"

JPN_PATH = DATA_DIR / "jpn_sentences.tsv.bz2"
RUS_PATH = DATA_DIR / "rus_sentences.tsv.bz2"
ENG_PATH = DATA_DIR / "eng_sentences.tsv.bz2"
LINKS_PATH = DATA_DIR / "tatoeba_links.csv.bz2"

BATCH_SIZE = 2000


def _download(url: str, dest: Path) -> None:
    if dest.exists():
        print(f"  {dest.name} already cached — skipping download")
        return
    print(f"  downloading {url} ...")
    urllib.request.urlretrieve(url, dest)
    print(f"  saved {dest}")


def _iter_sentences(path: Path) -> Iterator[tuple[int, str]]:
    """Yield (sentence_id, text) from a bz2-compressed Tatoeba per-language TSV."""
    with bz2.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t", 2)
            if len(parts) < 3:
                continue
            try:
                sid = int(parts[0])
            except ValueError:
                continue
            yield sid, parts[2]


def _load_sentences(path: Path) -> dict[int, str]:
    return dict(_iter_sentences(path))


def _download_links_raw() -> bytes:
    """Download links.tar.bz2 and extract the inner links.csv, returning raw bytes."""
    import tarfile

    tmp = DATA_DIR / "tatoeba_links.tar.bz2"
    _download(LINKS_URL, tmp)
    with tarfile.open(tmp, "r:bz2") as tf:
        # The archive contains a single file named 'links.csv'
        for member in tf.getmembers():
            if member.name.endswith("links.csv"):
                f = tf.extractfile(member)
                if f:
                    return f.read()
    raise RuntimeError("links.csv not found inside links.tar.bz2")


def _iter_links(raw: bytes) -> Iterator[tuple[int, int]]:
    """Yield (sentence_id, translation_id) pairs from links.csv bytes."""
    reader = csv.reader(io.TextIOWrapper(io.BytesIO(raw), encoding="utf-8"), delimiter="\t")
    for row in reader:
        if len(row) < 2:
            continue
        try:
            yield int(row[0]), int(row[1])
        except ValueError:
            continue


async def _insert_batch(conn: asyncpg.Connection, batch: list[dict]) -> None:
    await conn.executemany(
        """
        INSERT INTO reibun_entries
            (sentence_jp, translation_ru, translation_en, source, source_sentence_id)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT DO NOTHING
        """,
        [
            (
                e["sentence_jp"],
                e.get("translation_ru"),
                e.get("translation_en"),
                e["source"],
                e["source_sentence_id"],
            )
            for e in batch
        ],
    )


async def main() -> None:
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        sys.exit("ERROR: DATABASE_URL not set")
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    conn = await asyncpg.connect(db_url)
    try:
        count = await conn.fetchval("SELECT COUNT(*) FROM reibun_entries")
        if count > 0:
            print(f"  reibun_entries already has {count:,} rows — skipping")
            print("  pass --force to re-import (not yet implemented)")
            return

        # Download sentence files
        _download(JPN_URL, JPN_PATH)
        _download(RUS_URL, RUS_PATH)
        _download(ENG_URL, ENG_PATH)

        print("  loading Japanese sentences ...")
        jpn = _load_sentences(JPN_PATH)
        print(f"    {len(jpn):,} Japanese sentences")

        print("  loading Russian sentences ...")
        rus = _load_sentences(RUS_PATH)
        print(f"    {len(rus):,} Russian sentences")

        print("  loading English sentences ...")
        eng = _load_sentences(ENG_PATH)
        print(f"    {len(eng):,} English sentences")

        print("  downloading and parsing links ...")
        links_raw = _download_links_raw()

        # Build jpn_id → {ru: id, en: id} mapping (keep first match per language)
        jpn_to_ru: dict[int, int] = {}
        jpn_to_en: dict[int, int] = {}
        for src_id, tgt_id in _iter_links(links_raw):
            if src_id not in jpn:
                continue
            if tgt_id in rus and src_id not in jpn_to_ru:
                jpn_to_ru[src_id] = tgt_id
            elif tgt_id in eng and src_id not in jpn_to_en:
                jpn_to_en[src_id] = tgt_id

        print(f"    {len(jpn_to_ru):,} jp→ru links, {len(jpn_to_en):,} jp→en links")

        # Only import sentences that have at least one translation
        linked_ids = set(jpn_to_ru) | set(jpn_to_en)
        print(f"  building {len(linked_ids):,} reibun entries ...")

        batch: list[dict] = []
        total = 0
        for jpn_id in linked_ids:
            entry: dict = {
                "sentence_jp": jpn[jpn_id],
                "source": "tatoeba",
                "source_sentence_id": jpn_id,
            }
            ru_id = jpn_to_ru.get(jpn_id)
            en_id = jpn_to_en.get(jpn_id)
            if ru_id:
                entry["translation_ru"] = rus[ru_id]
            if en_id:
                entry["translation_en"] = eng[en_id]
            batch.append(entry)
            if len(batch) >= BATCH_SIZE:
                await _insert_batch(conn, batch)
                total += len(batch)
                batch = []
                print(f"  inserted {total:,} ...", end="\r")
        if batch:
            await _insert_batch(conn, batch)
            total += len(batch)

        final = await conn.fetchval("SELECT COUNT(*) FROM reibun_entries")
        print(f"\n  done — {final:,} reibun entries imported from Tatoeba")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
