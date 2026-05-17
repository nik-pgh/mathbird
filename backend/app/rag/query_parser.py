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
            self.page_number is not None
            or self.exercise_number
            or self.example_number
            or self.section_title
        )


PAGE_PATTERNS = [
    re.compile(r"\bpage\s+(\d+)\b", re.IGNORECASE),
    re.compile(r"\bp\.\s*(\d+)\b", re.IGNORECASE),
    re.compile(r"\bpg\.?\s*(\d+)\b", re.IGNORECASE),
]

EXERCISE_PATTERNS = [
    re.compile(r"\bproblem\s+(?:number\s+)?([A-Za-z]?\d+[A-Za-z]?)\b", re.IGNORECASE),
    re.compile(r"\bexercise\s+(?:number\s+)?([A-Za-z]?\d+[A-Za-z]?)\b", re.IGNORECASE),
    re.compile(r"\bquestion\s+(?:number\s+)?([A-Za-z]?\d+[A-Za-z]?)\b", re.IGNORECASE),
    re.compile(r"(?<!\w)#\s*([A-Za-z]?\d+[A-Za-z]?)\b", re.IGNORECASE),
]

EXAMPLE_PATTERN = re.compile(
    r"\bexample\s+(?:number\s+)?([A-Za-z]?\d+[A-Za-z]?)\b", re.IGNORECASE
)

# LLMs sampled from voice transcripts will sometimes spell numbers out
# ("question three", "page seven") instead of using digits, even when
# instructed to use digits. Pre-substituting these into the query lets the
# patterns above fire and the structured Qdrant lookup kick in. Covers 1–20,
# which spans all realistic problem / page / example references in a typical
# assignment or chapter. Larger numbers stay as words and fall back to
# semantic search.
NUMBER_WORDS: dict[str, str] = {
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "eleven": "11",
    "twelve": "12",
    "thirteen": "13",
    "fourteen": "14",
    "fifteen": "15",
    "sixteen": "16",
    "seventeen": "17",
    "eighteen": "18",
    "nineteen": "19",
    "twenty": "20",
}

_NUMBER_WORD_RE = re.compile(
    r"\b(" + "|".join(NUMBER_WORDS) + r")\b",
    re.IGNORECASE,
)


def _normalize_number_words(text: str) -> str:
    return _NUMBER_WORD_RE.sub(lambda m: NUMBER_WORDS[m.group(1).lower()], text)


def _first_match(patterns: list[re.Pattern[str]], text: str) -> str:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group(1)
    return ""


def parse_retrieval_query(query: str) -> ParsedRetrievalQuery:
    # Normalise spelled-out numbers before matching so "problem three" and
    # "page seven" reach the structured lookup the same as "problem 3" /
    # "page 7" would. The original ``query`` is preserved on the result for
    # the semantic-search fallback.
    normalized = _normalize_number_words(query)

    page = _first_match(PAGE_PATTERNS, normalized)
    exercise = _first_match(EXERCISE_PATTERNS, normalized)
    example_match = EXAMPLE_PATTERN.search(normalized)

    return ParsedRetrievalQuery(
        query=query,
        page_number=int(page) if page else None,
        exercise_number=exercise,
        example_number=example_match.group(1) if example_match else "",
    )
