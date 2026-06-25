"""Shared textbook reference-id extraction for ingest and query parsing."""

from __future__ import annotations

import re

EXERCISE_LABEL_RE = re.compile(
    r"\b(?:problem|exercise|question)\s+(?:number\s+)?([A-Za-z]?\d+[A-Za-z]?)\b",
    re.I,
)
EXERCISE_LIST_RE = re.compile(
    r"(?:^|\n)\s*\(([A-Za-z]?\d+[A-Za-z]?)\)\s+"
    r"|(?:^|\n)\s*([A-Za-z]?\d+[A-Za-z]?)[.)]\s+",
    re.I,
)

EXAMPLE_RE = re.compile(
    r"\bexample\s+(?:number\s+)?(\d+(?:\.\d+)?[A-Za-z]?)\b"
    r"|\b(\d+\.\d+)\s+example\b",
    re.I,
)

FIGURE_RE = re.compile(r"\bfigure\s+(\d+(?:\.\d+)?)\b", re.I)
FIGURE_ABBREV_RE = re.compile(r"\bfig\.?\s+(\d+(?:\.\d+)?)\b", re.I)

EQUATION_EXPLICIT_RE = re.compile(r"\bequation\s+(\d+\.\d+)\b", re.I)
EQUATION_ABBREV_RE = re.compile(r"\beq\.?\s+(\d+\.\d+)\b", re.I)
EQUATION_PAREN_RE = re.compile(r"\((\d+\.\d+)\)")

SECTION_HEADING_RE = re.compile(r"^\s*(\d+\.\d+)\b")
SECTION_QUERY_RE = re.compile(r"\bsection\s+(\d+\.\d+)\b", re.I)

FIGURE_QUERY_RE = re.compile(r"\bfigure\s+(\d+(?:\.\d+)?)\b", re.I)
FIGURE_QUERY_ABBREV_RE = re.compile(r"\bfig\.?\s+(\d+(?:\.\d+)?)\b", re.I)

EQUATION_QUERY_RE = re.compile(r"\bequation\s+(\d+\.\d+)\b", re.I)
EQUATION_QUERY_ABBREV_RE = re.compile(r"\beq\.?\s+(\d+\.\d+)\b", re.I)


def _first_group(match: re.Match[str] | None) -> str:
    if match is None:
        return ""
    return next((group for group in match.groups() if group), "")


def parse_section_number(text: str) -> str:
    """Return a section id such as ``2.7`` from a heading or explicit mention."""
    stripped = text.strip()
    if not stripped:
        return ""

    heading = SECTION_HEADING_RE.match(stripped)
    if heading:
        return heading.group(1)

    explicit = SECTION_QUERY_RE.search(stripped)
    if explicit:
        return explicit.group(1)

    return ""


def extract_exercise_number(
    text: str,
    markdown: str = "",
    *,
    allow_list_style: bool = True,
) -> str:
    haystack = f"{text}\n{markdown}"
    match = EXERCISE_LABEL_RE.search(haystack)
    if match:
        return match.group(1)
    if not allow_list_style:
        return ""
    list_match = EXERCISE_LIST_RE.search(haystack)
    return _first_group(list_match)


def extract_example_number(text: str, markdown: str = "") -> str:
    match = EXAMPLE_RE.search(f"{text}\n{markdown}")
    return _first_group(match)


def extract_figure_number(text: str, markdown: str = "") -> str:
    haystack = f"{text}\n{markdown}"
    for pattern in (FIGURE_RE, FIGURE_ABBREV_RE):
        match = pattern.search(haystack)
        if match:
            return match.group(1)
    return ""


def extract_equation_number(text: str, markdown: str = "") -> str:
    haystack = f"{text}\n{markdown}"
    for pattern in (EQUATION_EXPLICIT_RE, EQUATION_ABBREV_RE, EQUATION_PAREN_RE):
        match = pattern.search(haystack)
        if match:
            return match.group(1)
    return ""


def parse_section_query(text: str) -> str:
    return _first_group(SECTION_QUERY_RE.search(text))


def parse_figure_query(text: str) -> str:
    haystack = text
    for pattern in (FIGURE_QUERY_RE, FIGURE_QUERY_ABBREV_RE):
        match = pattern.search(haystack)
        if match:
            return match.group(1)
    return ""


def parse_equation_query(text: str) -> str:
    haystack = text
    for pattern in (EQUATION_QUERY_RE, EQUATION_QUERY_ABBREV_RE):
        match = pattern.search(haystack)
        if match:
            return match.group(1)
    return ""
