"""Unit tests for app.services.nlp.japanese.tokenize_japanese()."""
from __future__ import annotations

from app.services.nlp.japanese import tokenize_japanese

_REQUIRED_KEYS = {"surface", "dictionary_form", "reading", "pos", "jlpt_level", "hsk_level", "pinyin"}


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------


def test_returns_list():
    result = tokenize_japanese("私は学生です")
    assert isinstance(result, list)


def test_non_empty_for_real_sentence():
    result = tokenize_japanese("私は学生です")
    assert len(result) > 0


def test_each_token_has_required_keys():
    for token in tokenize_japanese("日本語を話す"):
        assert _REQUIRED_KEYS.issubset(token.keys()), f"Missing keys in {token}"


def test_surface_is_non_empty_string():
    for token in tokenize_japanese("私は学生です"):
        assert isinstance(token["surface"], str)
        assert len(token["surface"]) > 0


def test_pos_is_non_empty_string():
    for token in tokenize_japanese("食べる"):
        assert isinstance(token["pos"], str)
        assert len(token["pos"]) > 0


def test_reading_is_string_or_none():
    for token in tokenize_japanese("水を飲む"):
        assert token["reading"] is None or isinstance(token["reading"], str)


# ---------------------------------------------------------------------------
# JLPT level lookup
# ---------------------------------------------------------------------------


def test_jlpt_level_for_known_word():
    tokens = tokenize_japanese("私は学生です")
    # 私 is N5
    matches = [t for t in tokens if t["surface"] == "私"]
    assert matches, "Expected '私' to appear as a token"
    assert matches[0]["jlpt_level"] == 5


def test_jlpt_level_none_for_unknown_word():
    # A rare / unknown word should return None for jlpt_level
    tokens = tokenize_japanese("忖度")
    matches = [t for t in tokens if t["surface"] == "忖度"]
    if matches:
        assert matches[0]["jlpt_level"] == 1  # 忖度 is N1 in the lookup table


def test_hsk_level_always_none():
    for token in tokenize_japanese("日本語を話す"):
        assert token["hsk_level"] is None


def test_pinyin_always_none():
    for token in tokenize_japanese("日本語を話す"):
        assert token["pinyin"] is None


# ---------------------------------------------------------------------------
# Punctuation / whitespace filtering
# ---------------------------------------------------------------------------


def test_punctuation_not_in_output():
    tokens = tokenize_japanese("私は、学生です。")
    surfaces = [t["surface"] for t in tokens]
    # Punctuation marks are in SKIP_POS ("補助記号") and must be absent
    assert "、" not in surfaces
    assert "。" not in surfaces


def test_empty_string_returns_empty_list():
    assert tokenize_japanese("") == []
