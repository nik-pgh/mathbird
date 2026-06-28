"""Small deterministic parser for structured textbook references."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.rag.cardinal_words import CARDINAL_TOKEN, parse_cardinal_words
from app.rag.chapter import parse_chapter_number
from app.rag.reference_ids import (
    parse_equation_query,
    parse_figure_query,
    parse_section_query,
)


@dataclass(frozen=True)
class ParsedRetrievalQuery:
    query: str
    page_number: int | None = None
    chapter_number: int | None = None
    section_number: str = ""
    exercise_number: str = ""
    example_number: str = ""
    figure_number: str = ""
    equation_number: str = ""
    section_title: str = ""

    @property
    def is_structured_lookup(self) -> bool:
        return bool(
            self.page_number is not None
            or self.chapter_number is not None
            or self.section_number
            or self.exercise_number
            or self.example_number
            or self.figure_number
            or self.equation_number
            or self.section_title
        )


PAGE_PATTERNS = [
    re.compile(rf"\bpage\s+({CARDINAL_TOKEN})\b", re.IGNORECASE),
    re.compile(rf"\bp\.\s*({CARDINAL_TOKEN})\b", re.IGNORECASE),
    re.compile(rf"\bpg\.?\s*({CARDINAL_TOKEN})\b", re.IGNORECASE),
]

EXERCISE_PATTERNS = [
    re.compile(
        rf"\bproblem\s+(?:number\s+)?({CARDINAL_TOKEN}|[A-Za-z]?\d+[A-Za-z]?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\bexercise\s+(?:number\s+)?({CARDINAL_TOKEN}|[A-Za-z]?\d+[A-Za-z]?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\bquestion\s+(?:number\s+)?({CARDINAL_TOKEN}|[A-Za-z]?\d+[A-Za-z]?)\b",
        re.IGNORECASE,
    ),
    re.compile(rf"(?<!\w)#\s*({CARDINAL_TOKEN}|[A-Za-z]?\d+[A-Za-z]?)\b", re.IGNORECASE),
]

EXAMPLE_PATTERNS = [
    re.compile(r"\bexample\s+(?:number\s+)?(\d+(?:\.\d+)?[A-Za-z]?)\b", re.IGNORECASE),
    re.compile(r"\b(\d+\.\d+)\s+example\b", re.IGNORECASE),
    re.compile(rf"\bexample\s+(?:number\s+)?({CARDINAL_TOKEN})\b", re.IGNORECASE),
]


def _parse_cardinal_token(token: str) -> int | None:
    if token.isdigit():
        return int(token)
    return parse_cardinal_words(token)


def _parse_alphanumeric_token(token: str) -> str:
    if re.fullmatch(r"[A-Za-z]?\d+[A-Za-z]?", token):
        return token
    value = _parse_cardinal_token(token)
    return str(value) if value is not None else ""


def _first_int_match(patterns: list[re.Pattern[str]], text: str) -> int | None:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            value = _parse_cardinal_token(match.group(1))
            if value is not None:
                return value
    return None


def _first_token_match(patterns: list[re.Pattern[str]], text: str) -> str:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            token = _parse_alphanumeric_token(match.group(1))
            if token:
                return token
    return ""


def _first_example_match(text: str) -> str:
    for pattern in EXAMPLE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        token = match.group(1)
        if re.fullmatch(r"\d+(?:\.\d+)?[A-Za-z]?", token):
            return token
        value = _parse_cardinal_token(token)
        if value is not None:
            return str(value)
    return ""


def parse_retrieval_query(query: str) -> ParsedRetrievalQuery:
    return ParsedRetrievalQuery(
        query=query,
        page_number=_first_int_match(PAGE_PATTERNS, query),
        chapter_number=parse_chapter_number(query),
        section_number=parse_section_query(query),
        exercise_number=_first_token_match(EXERCISE_PATTERNS, query),
        example_number=_first_example_match(query),
        figure_number=parse_figure_query(query),
        equation_number=parse_equation_query(query),
    )
