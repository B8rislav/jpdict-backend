# Data Sources

All corpora used in jpdict-backend and their provenance, licenses, and import scripts.

---

## JMdict (Japanese-Multilingual Dictionary)

| Field | Value |
|-------|-------|
| **Source** | JMdict Project — https://www.edrdg.org/wiki/index.php/JMdict-EDICT_Dictionary_Project |
| **Format** | XML (JMdict_e.gz) |
| **License** | Creative Commons Attribution-ShareAlike 4.0 (CC BY-SA 4.0) — EDRDG / Jim Breen |
| **Coverage** | ~180,000 Japanese entries with English and Russian glosses, JLPT levels, common-word flags |
| **Target table** | `jmdict_entries` |
| **Import script** | `scripts/import_jmdict.py` |
| **`make` target** | `make import-jmdict` |
| **Refresh cadence** | Infrequent; re-run manually when upstream releases a new dump |

---

## KANJIDIC2

| Field | Value |
|-------|-------|
| **Source** | KANJIDIC2 Project — https://www.edrdg.org/wiki/index.php/KANJIDIC_Project |
| **Format** | Gzip-compressed XML (kanjidic2.xml.gz) |
| **License** | Creative Commons Attribution-ShareAlike 4.0 (CC BY-SA 4.0) — EDRDG / Jim Breen |
| **Coverage** | ~13,000 kanji with stroke counts, JLPT levels, Kangxi radical numbers, on/kun readings, English meanings |
| **Target table** | `kanjidic_entries` |
| **Import script** | `scripts/import_kanjidic2.py` |
| **`make` target** | `make import-kanjidic` |
| **Refresh cadence** | Infrequent; re-run manually when upstream releases a new dump |

---

## KRADFILE (Kanji Radical Decomposition)

| Field | Value |
|-------|-------|
| **Source** | KRADFILE — https://www.edrdg.org/krad/kradinf.html |
| **Format** | Plain text |
| **License** | Creative Commons Attribution-ShareAlike 4.0 (CC BY-SA 4.0) — EDRDG |
| **Coverage** | Component decomposition (radicals/components) for ~13,000 kanji |
| **Target table** | `kanjidic_entries.components` (UPDATE; must run after `import-kanjidic`) |
| **Import script** | `scripts/import_kradfile.py` |
| **`make` target** | `make import-kradfile` |
| **Refresh cadence** | Rarely changes; re-run only if KRADFILE is updated upstream |

---

## CC-CEDICT (Chinese-English Dictionary)

| Field | Value |
|-------|-------|
| **Source** | CC-CEDICT — https://cc-cedict.org |
| **Format** | Plain text (CC-CEDICT format) |
| **License** | Creative Commons Attribution-ShareAlike 4.0 (CC BY-SA 4.0) |
| **Coverage** | ~120,000 Chinese entries (traditional + simplified + pinyin + English definitions) |
| **Target table** | `cedict_entries` |
| **Import script** | `scripts/import_cedict.py` |
| **`make` target** | `make import-cedict` |
| **Refresh cadence** | Monthly releases; re-run when a new dump is available |

---

## HSK Wordlist (Hànyǔ Shuǐpíng Kǎoshì)

| Field | Value |
|-------|-------|
| **Source** | Community-maintained HSK 1–6 wordlist |
| **Format** | JSON / CSV |
| **License** | Public domain / community |
| **Coverage** | HSK levels 1–6 for ~5,000 common Chinese vocabulary items |
| **Target table** | `cedict_entries.hsk_level` + `cedict_entries.definitions.ru` (UPDATE; must run after `import-cedict`) |
| **Import script** | `scripts/import_hsk.py` |
| **`make` target** | `make import-hsk` |
| **Refresh cadence** | Stable; re-run only if the HSK standard is revised |

---

## Tatoeba (Example Sentences)

| Field | Value |
|-------|-------|
| **Source** | Tatoeba Project — https://tatoeba.org / https://downloads.tatoeba.org/exports/ |
| **Format** | TSV dumps: `jpn_sentences.tsv` (Japanese sentences), `rus_sentences.tsv` (Russian sentences), `eng_sentences.tsv` (English sentences), `links.csv` (translation pairs) |
| **License** | Creative Commons Attribution 2.0 France (CC BY 2.0 FR) — Tatoeba contributors |
| **Coverage** | ~200,000 Japanese sentences with Russian and/or English translations; stored in `reibun_entries` |
| **Target table** | `reibun_entries` |
| **Import script** | `scripts/import_tatoeba.py` |
| **`make` target** | `make import-reibun` |
| **Refresh cadence** | Quarterly; Tatoeba publishes regular dumps at the same URL |

### Why Tatoeba

Tatoeba was chosen over the alternatives (OpenSubtitles ja-ru via OPUS, custom Reibun corpora) because:

- Publicly downloadable per-language TSV dumps with stable URLs — no manual step required.
- Permissive CC BY 2.0 FR license compatible with the project's existing corpus licenses.
- Good jpn↔rus coverage (~20,000–40,000 pairs), and dense jpn↔eng coverage as a fallback.
- Human-authored, natural sentences — better quality than subtitle corpora for a dictionary use-case.

OpenSubtitles ja-ru (OPUS) was rejected because its sentence alignment is noisy and the download pipeline is more complex. A dedicated Reibun corpus was considered but is not freely available in machine-readable form.

### Fallback logic

`GET /api/reibun/search/{word_id}` returns:
- `translation` + `translation_lang: "ru"` when a Russian translation is available.
- `translation` + `translation_lang: "en"` when only an English translation exists.

---

## Russian Kanji Glosses (JMdict-derived)

| Field | Value |
|-------|-------|
| **Source** | Derived from JMdict Russian glosses already imported into `jmdict_entries` |
| **Format** | SQL query against the local PostgreSQL database — no external download |
| **License** | CC BY-SA 4.0 (same as JMdict) |
| **Coverage** | Russian meanings for all kanji that appear as a primary headword in JMdict (~2,000–3,000 common/JLPT kanji); stored in `kanjidic_entries.meanings_ru` |
| **Target table** | `kanjidic_entries.meanings_ru` (UPDATE; must run after `import-jmdict` and `import-kanjidic`) |
| **Import script** | `scripts/import_kanji_ru.py` |
| **`make` target** | `make import-kanji-ru` |
| **Refresh cadence** | Re-run after any JMdict update to pick up new or improved Russian glosses |

### How it works

For each kanji, the script finds the best JMdict entry:

1. Prefers entries whose sole kanji form is the character itself (e.g. 猫 → ねこ → кошка)
2. Falls back to entries where the character is the first kanji form of a compound
3. Within each rank, prefers common words then JLPT-ranked words

Russian glosses (up to 5) are extracted from the `ru` array inside each JMdict sense and written to `kanjidic_entries.meanings_ru`.  Re-running the script is safe (UPDATE in-place).

### Why not Yarxi?

Yarxi (yarxi.ru) is the natural first choice for per-kanji Russian glosses — it covers ~6,500 kanji with concise Russian meanings derived from Mescheryakov's authoritative dictionary.  However, the `yarxi.db` SQLite file is only distributed inside the Android APK and has no public standalone download URL.  JMdict-derived glosses provide equivalent quality for all JLPT kanji (the primary use-case) without requiring a manual file acquisition step.

If you obtain `yarxi.db` manually (e.g. extracted from the APK), a Yarxi-based importer can be added later.

### Fallback logic

`GET /api/kanji/{char}` returns:
- `meanings_ru` — Russian glosses (may be empty `[]` if no JMdict entry covers this kanji)
- `meanings` — `meanings_ru` when non-empty, otherwise `meanings_en` (KANJIDIC2 English)

This ensures the frontend always has a non-empty primary meanings list regardless of coverage.
