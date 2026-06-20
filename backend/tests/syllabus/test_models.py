"""Tests for syllabus pydantic models."""

from __future__ import annotations

from app.syllabus.models import Chapter, Concept, Problem, Syllabus


def test_syllabus_json_round_trip() -> None:
    syllabus = Syllabus(
        doc_id="doc-1",
        built_at="2026-06-19T00:00:00+00:00",
        chapters=[
            Chapter(
                id="ch-2",
                number=2,
                title="Chapter 2",
                concepts=[
                    Concept(
                        id="ch-2-c-fractions",
                        title="Fractions",
                        block_ids=("doc-1:p10:b0",),
                        problems=[
                            Problem(
                                id="ch-2-p-3",
                                kind="exercise",
                                label="Problem 3",
                                block_id="doc-1:p10:b1",
                                page_number=10,
                                exercise_number="3",
                            )
                        ],
                    )
                ],
            )
        ],
    )
    restored = Syllabus.model_validate(syllabus.model_dump(mode="json"))
    assert restored.doc_id == "doc-1"
    assert restored.chapters[0].concepts[0].problems[0].label == "Problem 3"
