"""Small deterministic parser for structured textbook references."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedRetrievalQuery:
    query: str
    page_number: int | None = None
    exercise_number: str = ""
    section_title: str = ""
    example_number: str = ""

    @property
    def is_structured_lookup(self) -> bool:
        return bool(
            self.page_number or self.exercise_number or self.example_number or self.section_title
        )


PAGE_PATTERNS = [
    re.compile(r"\bpage\s+(\d+)\b", re.IGNORECASE),
    re.compile(r"\bp\.\s*(\d+)\b", re.IGNORECASE),
    re.compile(r"\bpg\.?\s*(\d+)\b", re.IGNORECASE),
]

EXERCISE_PATTERNS = [
    re.compile(r"\bproblem\s+([A-Za-z]?\d+[A-Za-z]?)\b", re.IGNORECASE),
    re.compile(r"\bexercise\s+([A-Za-z]?\d+[A-Za-z]?)\b", re.IGNORECASE),
    re.compile(r"\bquestion\s+([A-Za-z]?\d+[A-Za-z]?)\b", re.IGNORECASE),
    re.compile(r"\b#\s*([A-Za-z]?\d+[A-Za-z]?)\b", re.IGNORECASE),
]

EXAMPLE_PATTERN = re.compile(r"\bexample\s+([A-Za-z]?\d+[A-Za-z]?)\b", re.IGNORECASE)


def _first_match(patterns: list[re.Pattern[str]], text: str) -> str:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group(1)
    return ""


def parse_retrieval_query(query: str) -> ParsedRetrievalQuery:
    page = _first_match(PAGE_PATTERNS, query)
    exercise = _first_match(EXERCISE_PATTERNS, query)
    example_match = EXAMPLE_PATTERN.search(query)

    return ParsedRetrievalQuery(
        query=query,
        page_number=int(page) if page else None,
        exercise_number=exercise,
        example_number=example_match.group(1) if example_match else "",
    )
