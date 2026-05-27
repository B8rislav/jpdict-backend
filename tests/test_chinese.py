"""Unit tests for app.services.nlp.chinese.tokenize_chinese()."""
from __future__ import annotations

from app.services.nlp.chinese import tokenize_chinese

_REQUIRED_KEYS = {"surface", "dictionary_form", "reading", "pos", "jlpt_level", "hsk_level", "pinyin"}


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------


def test_returns_list():
    result = tokenize_chinese("我爱中国")
    assert isinstance(result, list)


def test_non_empty_for_real_sentence():
    result = tokenize_chinese("我爱中国")
    assert len(result) > 0


def test_each_token_has_required_keys():
    for token in tokenize_chinese("我是学生"):
        assert _REQUIRED_KEYS.issubset(token.keys()), f"Missing keys in {token}"


def test_surface_is_non_empty_string():
    for token in tokenize_chinese("你好世界"):
        assert isinstance(token["surface"], str)
        assert len(token["surface"]) > 0


def test_pos_is_non_empty_string():
    for token in tokenize_chinese("我爱中国"):
        assert isinstance(token["pos"], str)
        assert len(token["pos"]) > 0


# ---------------------------------------------------------------------------
# Chinese-specific field contracts
# ---------------------------------------------------------------------------


def test_dictionary_form_equals_surface():
    # Chinese has no inflection; dictionary_form mirrors surface
    for token in tokenize_chinese("你好世界"):
        assert token["dictionary_form"] == token["surface"]


def test_reading_is_none():
    # Chinese tokens carry pinyin, not a separate reading field
    for token in tokenize_chinese("我爱中国"):
        assert token["reading"] is None


def test_jlpt_level_always_none():
    for token in tokenize_chinese("我爱中国"):
        assert token["jlpt_level"] is None


# ---------------------------------------------------------------------------
# Pinyin conversion
# ---------------------------------------------------------------------------


def test_pinyin_present():
    for token in tokenize_chinese("你好"):
        assert token["pinyin"] is not None
        assert len(token["pinyin"]) > 0


def test_pinyin_contains_tone_marks():
    tokens = tokenize_chinese("你好")
    # At least one token should have a tone-marked vowel (ā á ǎ à ō ó ǒ ò …)
    combined = "".join(t["pinyin"] for t in tokens)
    tone_chars = set("āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ")
    assert any(c in tone_chars for c in combined), f"No tone marks found in '{combined}'"


# ---------------------------------------------------------------------------
# HSK level lookup
# ---------------------------------------------------------------------------


def test_hsk_level_for_known_word():
    tokens = tokenize_chinese("我")
    matches = [t for t in tokens if t["surface"] == "我"]
    # jieba may merge or not — just check at least one token exists
    assert len(tokens) > 0
    # If 我 appears as its own token, it must be HSK1
    for m in matches:
        assert m["hsk_level"] == 1


def test_hsk_level_none_for_unknown_word():
    # A foreign-script word should have no HSK level
    tokens = tokenize_chinese("hello")
    for t in tokens:
        assert t["hsk_level"] is None


# ---------------------------------------------------------------------------
# Punctuation / whitespace filtering
# ---------------------------------------------------------------------------


def test_punctuation_filtered_out():
    # The pos=="x" filter removes punctuation tokens produced by jieba
    tokens = tokenize_chinese("你好，世界！")
    surfaces = [t["surface"] for t in tokens]
    assert "，" not in surfaces
    assert "！" not in surfaces


def test_empty_string_returns_empty_list():
    assert tokenize_chinese("") == []
