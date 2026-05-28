# NLP Pipeline

The NLP pipeline lives in `app/services/nlp/` and is invoked by `POST /api/analyze`.

## 1. Classifier (`app/services/nlp/classifier.py`)

Determines the query type by inspecting Unicode code points — no ML, no external calls.

### Unicode ranges

| Range | Block |
|---|---|
| U+3040–U+309F | Hiragana |
| U+30A0–U+30FF | Katakana |
| U+4E00–U+9FFF | CJK Unified Ideographs (main block) |
| U+3400–U+4DBF | CJK Extension A (rare kanji) |
| U+20000–U+2A6DF | CJK Extension B (historical / variant kanji) |
| U+F900–U+FAFF | CJK Compatibility Ideographs |

### Query types

| `QueryType` | Condition | Example |
|---|---|---|
| `KANJI` | `language == "jp"` and exactly one CJK character | `猫` |
| `HANZI` | `language == "cn"` and exactly one CJK character | `猫` |
| `SENTENCE` | any kana or CJK, more than one character | `今日は暑い`, `我爱你` |
| `REVERSE` | no kana, no CJK (romaji or English input) | `cat`, `neko` |

The `query_type` field in `AnalyzeResponse` reflects this classification.

---

## 2. Japanese tokenizer (`app/services/nlp/japanese.py`)

### Library

[SudachiPy](https://github.com/WorksApplications/SudachiPy) with SudachiDict-core.

### Tokenization mode

Mode **C** — splits compound words into their shortest recognized dictionary units.

> Mode A gives the finest split; mode C gives longer, more natural compounds. Mode C is used so that e.g. `東京都` returns `["東京都"]` rather than `["東京", "都"]`.

### Output per token

| Field | Source |
|---|---|
| `surface` | Raw text span |
| `dictionary_form` | SudachiPy `dictionary_form()` |
| `reading` | SudachiPy `reading_form()` (katakana) |
| `pos` | First element of `SudachiPy.part_of_speech()` |
| `jlpt_level` | Looked up from `JLPT_DICT` (see below) |
| `hsk_level` | Always `null` for Japanese |
| `pinyin` | Always `null` for Japanese |

### JLPT lookup

`JLPT_DICT` in `japanese.py` is a hardcoded dict mapping `dictionary_form` → level (1–5). The starter dict covers ~50 high-frequency words. It is extended at import time by `import_jmdict.py` which populates `jmdict_entries.jlpt_level`; the service queries the DB for unknown tokens on a cache miss (Phase 5 plan).

Tokens with POS `補助記号` (supplementary symbol) or `空白` (whitespace) are skipped.

---

## 3. Chinese tokenizer (`app/services/nlp/chinese.py`)

### Libraries

| Library | Role |
|---|---|
| [jieba](https://github.com/fxsjy/jieba) | Word segmentation + POS tagging (`jieba.posseg`) |
| [pypinyin](https://github.com/mozillazg/python-pinyin) | Pinyin generation with tone marks |

### Output per token

| Field | Source |
|---|---|
| `surface` | Raw text span |
| `dictionary_form` | Same as `surface` (jieba does not return base forms) |
| `reading` | Always `null` for Chinese |
| `pos` | jieba POS tag (Penn Treebank–style) |
| `jlpt_level` | Always `null` for Chinese |
| `hsk_level` | Looked up from `HSK_DICT` (see below) |
| `pinyin` | `pypinyin.Style.TONE` converted to diacritics via `pinyin.py` |

### Pinyin conversion

`pypinyin` outputs numbered tones (`wo3`). `app/services/pinyin.py:convert_pinyin()` maps tone suffixes to combining diacritic characters (`wǒ`). Neutral tone (5) is left without a diacritic.

### HSK lookup

`HSK_DICT` in `chinese.py` is a hardcoded dict of ~100 HSK1–6 words. It is extended by `import_hsk.py` which writes ~5,000 entries into `cedict_entries.hsk_level`; lookups beyond the starter dict query the DB.

Tokens with POS `x` (non-word symbols) are skipped.

---

## Known caveats

| Issue | Detail |
|---|---|
| Mixed-script queries | A query like `猫ねこ` (kanji + kana) routes as `SENTENCE`, not `KANJI`. This is correct behavior but users expecting a single kanji card must submit just `猫`. |
| Traditional vs. simplified detection | The Chinese tokenizer does not distinguish scripts — the frontend passes `lang=cn` (simplified) or `lang=cn_traditional` (traditional), and the search router routes accordingly. The analyzer always runs jieba regardless of script. |
| JLPT starter dict | Only ~50 words are hardcoded. Tokens not in `jmdict_entries` with a `jlpt_level` will show `null`. |
| HSK starter dict | Only ~100 words are hardcoded. Coverage depends on `import_hsk` having run. |
| Compound word boundaries | SudachiPy mode C can over-compound in some edge cases (e.g. names embedded in longer strings). |
| Jieba custom dictionary | No project-specific jieba user dict is loaded; domain-specific terms (e.g. JLPT exam vocabulary) may segment incorrectly. |
