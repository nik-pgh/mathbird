"""Build a syllabus tree from normalized ParsedDocument blocks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.rag.parsing import BlockType, ParsedBlock, ParsedDocument
from app.syllabus.models import Chapter, Concept, Problem, Syllabus

_DEFAULT_CONCEPT_TITLE = "General"
_PROBLEM_BLOCK_TYPES: frozenset[BlockType] = frozenset({"exercise", "example"})


def _slug(value: str, *, prefix: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return f"{prefix}-{cleaned[:48]}" if cleaned else prefix


def _chapter_id(number: int | None, title: str) -> str:
    if number is not None:
        return f"ch-{number}"
    return _slug(title or "untitled", prefix="ch")


def _problem_label(block: ParsedBlock) -> str:
    if block.exercise_number:
        return f"Problem {block.exercise_number}"
    if block.example_number:
        return f"Example {block.example_number}"
    preview = block.text.strip().splitlines()[0][:40] if block.text.strip() else block.block_id
    return preview or block.block_id


def _problem_id(chapter_id: str, block: ParsedBlock) -> str:
    token = block.exercise_number or block.example_number or block.block_id.split(":")[-1]
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "-", token).strip("-") or "item"
    return f"{chapter_id}-p-{safe}"


@dataclass
class _ConceptBuilder:
    id: str
    title: str
    block_ids: list[str] = field(default_factory=list)
    problems: list[Problem] = field(default_factory=list)


@dataclass
class _ChapterBuilder:
    id: str
    number: int | None
    title: str
    concepts: list[_ConceptBuilder] = field(default_factory=list)


def _iter_blocks(document: ParsedDocument) -> list[ParsedBlock]:
    blocks: list[ParsedBlock] = []
    for page in document.pages:
        blocks.extend(page.blocks)
    return blocks


def _ensure_concept(chapter: _ChapterBuilder, *, title: str) -> _ConceptBuilder:
    if chapter.concepts and chapter.concepts[-1].title == title:
        return chapter.concepts[-1]
    concept = _ConceptBuilder(id=_slug(title, prefix=f"{chapter.id}-c"), title=title)
    chapter.concepts.append(concept)
    return concept


def _ensure_chapter(
    chapters: list[_ChapterBuilder],
    *,
    number: int | None,
    title: str,
) -> _ChapterBuilder:
    chapter_id = _chapter_id(number, title)
    if chapters and chapters[-1].id == chapter_id:
        return chapters[-1]
    chapter = _ChapterBuilder(id=chapter_id, number=number, title=title)
    chapters.append(chapter)
    return chapter


def build_heuristic_syllabus(document: ParsedDocument) -> Syllabus:
    """Deterministic pass-1 syllabus from parsed textbook blocks."""
    chapter_builders: list[_ChapterBuilder] = []
    current_chapter_number: int | None = None
    current_chapter_title = "Chapter 1"
    current_concept_title = _DEFAULT_CONCEPT_TITLE

    for block in _iter_blocks(document):
        if block.chapter_number:
            if current_chapter_number != block.chapter_number:
                current_chapter_number = block.chapter_number
                current_chapter_title = f"Chapter {block.chapter_number}"
                current_concept_title = _DEFAULT_CONCEPT_TITLE

        chapter = _ensure_chapter(
            chapter_builders,
            number=current_chapter_number,
            title=current_chapter_title,
        )

        if block.block_type == "heading":
            heading = block.section_title or block.text.strip() or current_concept_title
            current_concept_title = heading
            _ensure_concept(chapter, title=current_concept_title)
            continue

        concept = _ensure_concept(chapter, title=current_concept_title)

        if block.block_type in _PROBLEM_BLOCK_TYPES:
            kind = "exercise" if block.block_type == "exercise" else "example"
            concept.problems.append(
                Problem(
                    id=_problem_id(chapter.id, block),
                    kind=kind,
                    label=_problem_label(block),
                    block_id=block.block_id,
                    page_number=block.page_number,
                    exercise_number=block.exercise_number,
                    example_number=block.example_number,
                )
            )
            continue

        if block.block_type in {"paragraph", "equation", "instruction", "table", "image", "graph"}:
            concept.block_ids.append(block.block_id)

    if not chapter_builders:
        chapter_builders.append(
            _ChapterBuilder(id="ch-1", number=1, title="Chapter 1"),
        )
        _ensure_concept(chapter_builders[0], title=_DEFAULT_CONCEPT_TITLE)

    chapters = [
        Chapter(
            id=builder.id,
            number=builder.number,
            title=builder.title,
            concepts=[
                Concept(
                    id=concept.id,
                    title=concept.title,
                    block_ids=tuple(concept.block_ids),
                    problems=concept.problems,
                )
                for concept in builder.concepts
            ],
        )
        for builder in chapter_builders
    ]

    return Syllabus(
        doc_id=document.doc_id,
        built_at=datetime.now(UTC).isoformat(),
        chapters=chapters,
    )
