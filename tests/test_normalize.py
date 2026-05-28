"""Unit tests for normalize_reverse_query."""
from __future__ import annotations

import pytest

from app.services.search.normalize import NormalizedQuery, normalize_reverse_query


def test_strips_leading_article_a() -> None:
    result = normalize_reverse_query("a cat")
    assert result.text == "cat"


def test_strips_leading_article_an() -> None:
    result = normalize_reverse_query("an apple")
    assert result.text == "apple"


def test_strips_leading_article_the_and_lowercases() -> None:
    result = normalize_reverse_query("The Cats")
    assert result.text == "cats"


def test_cyrillic_detected_as_ru() -> None:
    result = normalize_reverse_query("кошка")
    assert result.script == "ru"


def test_latin_detected_as_en() -> None:
    result = normalize_reverse_query("cat")
    assert result.script == "en"


def test_ru_article_not_stripped() -> None:
    # Russian has no articles — normalization must not strip word prefixes
    result = normalize_reverse_query("кошка")
    assert result.text == "кошка"


def test_tokens_for_multi_word() -> None:
    result = normalize_reverse_query("to be")
    assert result.tokens == ["to", "be"]


def test_collapses_internal_whitespace() -> None:
    result = normalize_reverse_query("a  cat")
    assert result.text == "cat"
    assert result.tokens == ["cat"]


def test_strips_trailing_punctuation() -> None:
    result = normalize_reverse_query("cat.")
    assert result.text == "cat"


def test_strips_trailing_whitespace_and_punct() -> None:
    result = normalize_reverse_query("cat!  ")
    assert result.text == "cat"


def test_empty_string_raises() -> None:
    with pytest.raises(ValueError):
        normalize_reverse_query("")


def test_whitespace_only_raises() -> None:
    with pytest.raises(ValueError):
        normalize_reverse_query("   ")


def test_returns_normalized_query_type() -> None:
    result = normalize_reverse_query("a cat")
    assert isinstance(result, NormalizedQuery)
    assert result.script == "en"
    assert isinstance(result.tokens, list)
