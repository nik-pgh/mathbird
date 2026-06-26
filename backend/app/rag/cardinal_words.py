"""Parse English cardinal number words for structured reference extraction."""

from __future__ import annotations

import re

_ONES: dict[str, int] = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}

_TENS: dict[str, int] = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}

_ALL_WORDS = tuple(sorted({*_ONES, *_TENS, "hundred", "and"}, key=len, reverse=True))
_NUMBER_WORD = "(?:" + "|".join(_ALL_WORDS) + ")"
CARDINAL_WORDS = rf"{_NUMBER_WORD}(?:[\s-]+{_NUMBER_WORD})*"
# Digits or a run of number words (optionally hyphenated), e.g. "40", "forty",
# "forty-two", "one hundred twenty three".
CARDINAL_TOKEN = rf"(?:\d+|{CARDINAL_WORDS})"


def parse_cardinal_words(text: str) -> int | None:
    """Return a non-negative integer parsed from ``text``, or ``None`` if invalid."""
    cleaned = re.sub(r"[\s-]+", " ", text.strip().lower())
    if not cleaned:
        return None
    if cleaned.isdigit():
        value = int(cleaned)
        return value if value >= 0 else None

    total = 0
    current = 0
    for word in cleaned.split():
        if word == "and":
            continue
        if word == "hundred":
            current = max(current, 1) * 100
            continue
        if word in _ONES:
            current += _ONES[word]
            continue
        if word in _TENS:
            current += _TENS[word]
            continue
        return None

    total += current
    return total if total >= 0 else None
