"""Unit tests for app.services.nlp.classifier.classify()."""
from __future__ import annotations

import pytest

from app.services.nlp.classifier import QueryType, classify


# ---------------------------------------------------------------------------
# KANJI branch (jp + single CJK)
# ---------------------------------------------------------------------------


def test_single_cjk_jp_returns_kanji():
    assert classify("水", "jp") == QueryType.KANJI


def test_single_cjk_jp_uppercase_lang():
    assert classify("山", "JP") == QueryType.KANJI


# ---------------------------------------------------------------------------
# HANZI branch (cn + single CJK)
# ---------------------------------------------------------------------------


def test_single_cjk_cn_returns_hanzi():
    assert classify("水", "cn") == QueryType.HANZI


def test_single_cjk_cn_uppercase_lang():
    assert classify("山", "CN") == QueryType.HANZI


# ---------------------------------------------------------------------------
# SENTENCE branch
# ---------------------------------------------------------------------------


def test_multi_cjk_jp_returns_sentence():
    assert classify("食べ物", "jp") == QueryType.SENTENCE


def test_kana_only_jp_returns_sentence():
    # Hiragana has no CJK chars but has kana → SENTENCE (not REVERSE, not KANJI)
    assert classify("たべる", "jp") == QueryType.SENTENCE


def test_katakana_only_jp_returns_sentence():
    assert classify("テスト", "jp") == QueryType.SENTENCE


def test_mixed_cjk_kana_jp_returns_sentence():
    assert classify("日本語を話す", "jp") == QueryType.SENTENCE


def test_multi_cjk_cn_returns_sentence():
    assert classify("你好世界", "cn") == QueryType.SENTENCE


def test_single_cjk_unknown_lang_returns_kanji():
    # Unknown languages fall through to the KANJI default
    assert classify("水", "unknown") == QueryType.KANJI


def test_multi_cjk_unknown_lang_returns_sentence():
    assert classify("你好世界", "unknown") == QueryType.SENTENCE


# ---------------------------------------------------------------------------
# REVERSE branch (Latin / no CJK, no kana)
# ---------------------------------------------------------------------------


def test_latin_jp_returns_reverse():
    assert classify("hello", "jp") == QueryType.REVERSE


def test_latin_cn_returns_reverse():
    assert classify("water", "cn") == QueryType.REVERSE


def test_mixed_latin_spaces_returns_reverse():
    assert classify("good morning", "jp") == QueryType.REVERSE


# ---------------------------------------------------------------------------
# Edge cases — empty / whitespace
# ---------------------------------------------------------------------------


def test_empty_string_raises():
    with pytest.raises(ValueError):
        classify("", "jp")


def test_whitespace_only_raises():
    with pytest.raises(ValueError):
        classify("   ", "jp")


def test_tab_only_raises():
    with pytest.raises(ValueError):
        classify("\t\n", "cn")


# ---------------------------------------------------------------------------
# Mixed-script inputs
# ---------------------------------------------------------------------------


def test_latin_plus_cjk_jp_treated_as_sentence():
    # Contains CJK → not REVERSE; length > 1 → SENTENCE
    assert classify("abc水", "jp") == QueryType.SENTENCE


def test_latin_plus_kana_jp_treated_as_sentence():
    assert classify("abcたべる", "jp") == QueryType.SENTENCE
