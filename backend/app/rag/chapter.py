"""Shared chapter-number extraction for ingest and query parsing."""

from __future__ import annotations

import re

CHAPTER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bchapter\s+(\d+)\b", re.IGNORECASE),
    re.compile(r"\bchapter(\d+)\b", re.IGNORECASE),
    re.compile(r"\bCHAPTER(\d+)\.", re.IGNORECASE),
    re.compile(r"\bch\.?\s*(\d+)\b", re.IGNORECASE),
)


def parse_chapter_number(text: str) -> int | None:
    """Return the first chapter number found in ``text``, or ``None``."""
    for pattern in CHAPTER_PATTERNS:
        match = pattern.search(text)
        if match:
            return int(match.group(1))
    return None
