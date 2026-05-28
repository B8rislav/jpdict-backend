# Database

ERD-style reference for every table in the JpDict schema. PostgreSQL 15 with `pg_trgm` and `pgcrypto` extensions.

Extensions are enabled in migration [0001_initial_schema](../alembic/versions/0001_initial_schema.py).

---

## `users`

**Migration:** 0001_initial_schema

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK, default `gen_random_uuid()` |
| `email` | VARCHAR | NOT NULL, UNIQUE |
| `hashed_password` | VARCHAR | NOT NULL |
| `language` | `language_enum` | NOT NULL — `jp` or `cn` |
| `created_at` | TIMESTAMPTZ | NOT NULL, default `NOW()` |

No indexes beyond PK and unique email.

---

## `saved_words`

**Migration:** 0001_initial_schema

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK, default `gen_random_uuid()` |
| `user_id` | UUID | FK → `users.id` ON DELETE CASCADE |
| `language` | `language_enum` | NOT NULL |
| `expression` | TEXT | NOT NULL |
| `reading` | TEXT | NOT NULL |
| `meaning` | TEXT | NOT NULL |
| `jlpt_level` | SMALLINT | NULL or 1–5 |
| `hsk_level` | SMALLINT | NULL or 1–6 |
| `status` | `word_status` | NOT NULL, default `new` — `new`, `learning`, `known` |
| `added_at` | TIMESTAMPTZ | NOT NULL, default `NOW()` |

**Unique constraint:** `(user_id, language, expression)`

**Indexes:**
- `idx_saved_words_user_lang` — btree `(user_id, language)` — fast per-user per-language listing
- `idx_saved_words_expression_trgm` — **GIN trigram** `(expression)` — similarity search across saved vocabulary

---

## `search_history`

**Migration:** 0001_initial_schema

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK, default `gen_random_uuid()` |
| `user_id` | UUID | FK → `users.id` ON DELETE CASCADE |
| `language` | `language_enum` | NOT NULL |
| `query` | TEXT | NOT NULL |
| `query_type` | VARCHAR(20) | NOT NULL |
| `searched_at` | TIMESTAMPTZ | NOT NULL, default `NOW()` |

No additional indexes beyond PK. Queries are filtered by `user_id` and ordered by `searched_at DESC`.

---

## `kanji_cache`

**Migration:** 0001_initial_schema

Persistent cache for serialised `KanjiCard` objects (avoids repeated JMdict/KANJIDIC queries on hot kanji). Part of the two-level cache strategy: in-memory `TTLCache` (10 min) is checked first; this table is the second level with a 30-day expiry.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK, default `gen_random_uuid()` |
| `character` | VARCHAR(10) | NOT NULL, UNIQUE |
| `data` | JSONB | NOT NULL — serialised `KanjiCard` |
| `cached_at` | TIMESTAMPTZ | NOT NULL, default `NOW()` |
| `expires_at` | TIMESTAMPTZ | NOT NULL — `cached_at + 30 days` |

---

## `jmdict_entries`

**Migration:** 0002_dictionary_tables

~180,000 Japanese dictionary entries from JMdict.

| Column | Type | Constraints |
|---|---|---|
| `id` | SERIAL | PK |
| `entry_id` | INTEGER | NOT NULL, UNIQUE — original JMdict entry sequence number |
| `kanji_forms` | TEXT[] | NOT NULL, default `{}` — kanji headwords |
| `reading_forms` | TEXT[] | NOT NULL, default `{}` — kana readings |
| `senses` | JSONB | NOT NULL, default `[]` — array of `{pos, ru, en, field}` |
| `jlpt_level` | SMALLINT | NULL — 1 (N1) through 5 (N5) |
| `common` | BOOLEAN | NOT NULL, default `false` — high-frequency word flag |

**Indexes:**
- `idx_jmdict_kanji_gin` — **GIN** `(kanji_forms)` — `ANY` operator lookup
- `idx_jmdict_reading_gin` — **GIN** `(reading_forms)` — `ANY` operator lookup
- `idx_jmdict_jlpt` — btree `(jlpt_level)` — level filtering

---

## `kanjidic_entries`

**Migrations:** 0002_dictionary_tables (base), 0004_kanji_meanings_ru (`meanings_ru` column)

~13,000 kanji from KANJIDIC2, component data from KRADFILE.

| Column | Type | Constraints |
|---|---|---|
| `character` | TEXT | PK, CHECK `length(character) = 1` |
| `stroke_count` | SMALLINT | NULL |
| `jlpt_level` | SMALLINT | NULL — 1 (N1) through 5 (N5), remapped from KANJIDIC2's 4-level scale |
| `grade` | SMALLINT | NULL — school grade 1–6, 8 |
| `frequency` | SMALLINT | NULL — Jōyō frequency rank (1–2500) |
| `on_readings` | TEXT[] | NOT NULL, default `{}` — katakana on'yomi |
| `kun_readings` | TEXT[] | NOT NULL, default `{}` — hiragana kun'yomi |
| `meanings_en` | TEXT[] | NOT NULL, default `{}` — English glosses from KANJIDIC2 |
| `radical_number` | SMALLINT | NULL — Kangxi radical index (1–214) |
| `components` | TEXT[] | NOT NULL, default `{}` — graphical components from KRADFILE |
| `meanings_ru` | TEXT[] | NOT NULL, default `{}` — Russian glosses derived from JMdict (added in 0004) |

**Indexes:**
- `idx_kanjidic_jlpt` — btree `(jlpt_level)` — level filtering

---

## `cedict_entries`

**Migration:** 0003_cedict_entries

~120,000 Chinese entries from CC-CEDICT. Russian glosses and HSK levels added by `import_hsk.py`.

| Column | Type | Constraints |
|---|---|---|
| `id` | SERIAL | PK |
| `traditional` | TEXT | NOT NULL |
| `simplified` | TEXT | NOT NULL |
| `pinyin` | TEXT | NOT NULL — numbered tone format, e.g. `wo3 men5` |
| `definitions` | JSONB | NOT NULL, default `{}` — `{en: [...], ru: [...]}` |
| `hsk_level` | SMALLINT | NULL — 1–6 (populated by `import_hsk.py`) |

**Indexes:**
- `idx_cedict_simplified_gin` — **GIN trigram** `(simplified)` — similarity search
- `idx_cedict_traditional_gin` — **GIN trigram** `(traditional)` — similarity search
- `idx_cedict_hsk` — btree `(hsk_level)` — level filtering

---

## `reibun_entries`

**Migration:** 0005_reibun_entries

Japanese example sentences with Russian and/or English translations, sourced from Tatoeba.

| Column | Type | Constraints |
|---|---|---|
| `id` | BIGSERIAL | PK |
| `sentence_jp` | TEXT | NOT NULL |
| `reading_jp` | TEXT | NULL — furigana reading (not populated by Tatoeba import) |
| `translation_ru` | TEXT | NULL — Russian translation |
| `translation_en` | TEXT | NULL — English translation |
| `source` | TEXT | NOT NULL — source name, e.g. `tatoeba` |
| `source_sentence_id` | BIGINT | NULL — original ID in the source corpus |

**Indexes:**
- `idx_reibun_sentence_jp_gin` — **GIN trigram** `(sentence_jp)` — `ILIKE %expression%` search
- `idx_reibun_source_sentence_id` — btree `(source_sentence_id)` — deduplication on re-import

---

## Custom types (enums)

| Type | Values | Used by |
|---|---|---|
| `language_enum` | `jp`, `cn` | `users.language`, `saved_words.language`, `search_history.language` |
| `word_status` | `new`, `learning`, `known` | `saved_words.status` |

---

## FK relations summary

```
users ──< saved_words       (user_id, CASCADE DELETE)
users ──< search_history    (user_id, CASCADE DELETE)
```

Dictionary tables (`jmdict_entries`, `kanjidic_entries`, `cedict_entries`, `reibun_entries`) are standalone with no FK relations to user tables — denormalized for query efficiency.

---

## GIN / trigram indexes at a glance

| Table | Column | Type | Purpose |
|---|---|---|---|
| `saved_words` | `expression` | GIN trigram | Similarity search across saved vocab |
| `jmdict_entries` | `kanji_forms` | GIN array | `ANY` operator lookup by kanji form |
| `jmdict_entries` | `reading_forms` | GIN array | `ANY` operator lookup by kana reading |
| `cedict_entries` | `simplified` | GIN trigram | Prefix + similarity search |
| `cedict_entries` | `traditional` | GIN trigram | Prefix + similarity search |
| `reibun_entries` | `sentence_jp` | GIN trigram | `ILIKE` full-text containment |
