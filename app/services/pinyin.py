from __future__ import annotations

import re

_TONE_MARKS: dict[str, list[str]] = {
    "a": ["ā", "á", "ǎ", "à", "a"],
    "e": ["ē", "é", "ě", "è", "e"],
    "i": ["ī", "í", "ǐ", "ì", "i"],
    "o": ["ō", "ó", "ǒ", "ò", "o"],
    "u": ["ū", "ú", "ǔ", "ù", "u"],
    "v": ["ǖ", "ǘ", "ǚ", "ǜ", "ü"],  # CEDICT uses v for ü
}


def _syllable_with_tone(syllable: str, tone: int) -> str:
    if tone == 5:  # neutral tone — no diacritic
        return syllable.replace("v", "ü")
    for vowel in ("a", "e"):
        if vowel in syllable:
            return syllable.replace(vowel, _TONE_MARKS[vowel][tone - 1], 1)
    if "ou" in syllable:
        return syllable.replace("o", _TONE_MARKS["o"][tone - 1], 1)
    for char in reversed(syllable):
        if char in _TONE_MARKS:
            idx = syllable.rindex(char)
            return syllable[:idx] + _TONE_MARKS[char][tone - 1] + syllable[idx + 1 :]
    return syllable.replace("v", "ü")


def convert_pinyin(pinyin: str) -> str:
    """Convert numbered pinyin (wo3 men5) to diacritic pinyin (wǒ men)."""

    def replace(m: re.Match) -> str:
        return _syllable_with_tone(m.group(1), int(m.group(2)))

    return re.sub(r"([a-züv]+)([1-5])", replace, pinyin, flags=re.IGNORECASE)
