"""Shared chapter-number extraction for ingest and query parsing."""

from __future__ import annotations

import re

from app.rag.cardinal_words import CARDINAL_TOKEN, parse_cardinal_words

CHAPTER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(rf"\bchapter\s+({CARDINAL_TOKEN})\b", re.IGNORECASE),
    re.compile(r"\bchapter(\d+)\b", re.IGNORECASE),
    re.compile(r"\bCHAPTER(\d+)\.", re.IGNORECASE),
    re.compile(rf"\bch\.?\s*({CARDINAL_TOKEN})\b", re.IGNORECASE),
)


def _chapter_token_to_int(token: str) -> int | None:
    if token.isdigit():
        return int(token)
    return parse_cardinal_words(token)


def parse_chapter_number(text: str) -> int | None:
    """Return the first chapter number found in ``text``, or ``None``."""
    for pattern in CHAPTER_PATTERNS:
        match = pattern.search(text)
        if match:
            return _chapter_token_to_int(match.group(1))
    return None
