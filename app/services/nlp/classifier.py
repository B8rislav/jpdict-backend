from enum import Enum


class QueryType(str, Enum):
    KANJI = "KANJI"
    HANZI = "HANZI"
    SENTENCE = "SENTENCE"
    REVERSE = "REVERSE"


# Unicode range constants
HIRAGANA_START = 0x3040
HIRAGANA_END = 0x309F
KATAKANA_START = 0x30A0
KATAKANA_END = 0x30FF
CJK_START = 0x4E00
CJK_END = 0x9FFF
CJK_EXT_A_START = 0x3400
CJK_EXT_A_END = 0x4DBF
CJK_EXT_B_START = 0x20000
CJK_EXT_B_END = 0x2A6DF
CJK_COMPAT_START = 0xF900
CJK_COMPAT_END = 0xFAFF


def _is_cjk(ch: str) -> bool:
    cp = ord(ch)
    return (
        CJK_START <= cp <= CJK_END
        or CJK_EXT_A_START <= cp <= CJK_EXT_A_END
        or CJK_EXT_B_START <= cp <= CJK_EXT_B_END
        or CJK_COMPAT_START <= cp <= CJK_COMPAT_END
    )


def _is_hiragana(ch: str) -> bool:
    return HIRAGANA_START <= ord(ch) <= HIRAGANA_END


def _is_katakana(ch: str) -> bool:
    return KATAKANA_START <= ord(ch) <= KATAKANA_END


def classify(query: str, language: str) -> QueryType:
    """Classify a query by script + language into a QueryType (KANJI/HANZI/SENTENCE/REVERSE)."""
    stripped = query.strip()
    if not stripped:
        raise ValueError("Query must not be empty")

    has_cjk = any(_is_cjk(c) for c in stripped)
    has_kana = any(_is_hiragana(c) or _is_katakana(c) for c in stripped)

    if not has_cjk and not has_kana:
        return QueryType.REVERSE

    lang = language.lower()

    if lang == "jp":
        if len(stripped) == 1 and _is_cjk(stripped[0]):
            return QueryType.KANJI
        return QueryType.SENTENCE
    elif lang == "cn":
        if len(stripped) == 1 and _is_cjk(stripped[0]):
            return QueryType.HANZI
        return QueryType.SENTENCE
    else:
        if len(stripped) == 1 and _is_cjk(stripped[0]):
            return QueryType.KANJI
        return QueryType.SENTENCE
