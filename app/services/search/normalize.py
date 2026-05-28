from __future__ import annotations

import re
from dataclasses import dataclass

_ARTICLE_RE = re.compile(r"^(?:a|an|the)\s+", re.IGNORECASE)
_TRAILING_PUNCT_RE = re.compile(r"[\s.,;:!?\-]+$")
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass
class NormalizedQuery:
    text: str
    script: str  # 'en' or 'ru'
    tokens: list[str]


def normalize_reverse_query(q: str) -> NormalizedQuery:
    stripped = q.strip()
    if not stripped:
        raise ValueError("Query must not be empty")

    script = "ru" if any("Ѐ" <= c <= "ӿ" for c in stripped) else "en"

    normalized = _WHITESPACE_RE.sub(" ", stripped.lower())

    if script == "en":
        normalized = _ARTICLE_RE.sub("", normalized)

    normalized = _TRAILING_PUNCT_RE.sub("", normalized)

    if not normalized:
        raise ValueError("Query must not be empty after normalization")

    return NormalizedQuery(text=normalized, script=script, tokens=normalized.split())
