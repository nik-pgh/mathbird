"""Tests for heuristic syllabus builder."""

from __future__ import annotations

from app.rag.parsing import ParsedBlock, ParsedDocument, ParsedPage
from app.syllabus.builder import build_heuristic_syllabus


def _sample_document() -> ParsedDocument:
    return ParsedDocument(
        doc_id="doc-1",
        filename="book.pdf",
        pages=[
            ParsedPage(
                page_number=10,
                text="",
                blocks=[
                    ParsedBlock(
                        block_id="doc-1:p10:b0",
                        page_number=10,
                        block_type="heading",
                        text="Fractions",
                        section_title="Fractions",
                        chapter_number=2,
                    ),
                    ParsedBlock(
                        block_id="doc-1:p10:b1",
                        page_number=10,
                        block_type="paragraph",
                        text="A fraction represents parts of a whole.",
                        chapter_number=2,
                        section_title="Fractions",
                    ),
                    ParsedBlock(
                        block_id="doc-1:p10:b2",
                        page_number=10,
                        block_type="exercise",
                        text="Problem 3. Simplify 4/8.",
                        chapter_number=2,
                        exercise_number="3",
                        section_title="Fractions",
                    ),
                ],
            ),
            ParsedPage(
                page_number=20,
                text="",
                blocks=[
                    ParsedBlock(
                        block_id="doc-1:p20:b0",
                        page_number=20,
                        block_type="heading",
                        text="Decimals",
                        section_title="Decimals",
                        chapter_number=3,
                    ),
                    ParsedBlock(
                        block_id="doc-1:p20:b1",
                        page_number=20,
                        block_type="example",
                        text="Example 1. Write 0.5 as a fraction.",
                        chapter_number=3,
                        example_number="1",
                        section_title="Decimals",
                    ),
                ],
            ),
        ],
    )


def test_build_heuristic_syllabus_groups_chapters_concepts_and_problems() -> None:
    syllabus = build_heuristic_syllabus(_sample_document())

    assert syllabus.doc_id == "doc-1"
    assert len(syllabus.chapters) == 2
    assert syllabus.chapters[0].number == 2
    assert syllabus.chapters[0].concepts[0].title == "Fractions"
    assert syllabus.chapters[0].concepts[0].block_ids == ("doc-1:p10:b1",)
    assert len(syllabus.chapters[0].concepts[0].problems) == 1
    assert syllabus.chapters[0].concepts[0].problems[0].exercise_number == "3"
    assert syllabus.chapters[1].concepts[0].problems[0].kind == "example"
