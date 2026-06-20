"""Tests for ProgressEngine knowledge tracing."""

from __future__ import annotations

from app.progress.engine import ProgressEngine
from app.progress.models import FocusPointer, ProgressState
from app.syllabus.models import Chapter, Concept, Problem, Syllabus


def _syllabus() -> Syllabus:
    return Syllabus(
        doc_id="doc-1",
        built_at="2026-06-19T00:00:00+00:00",
        chapters=[
            Chapter(
                id="ch-1",
                number=1,
                title="Chapter 1",
                concepts=[
                    Concept(
                        id="ch-1-c-a",
                        title="Concept A",
                        problems=[
                            Problem(
                                id="ch-1-p-1",
                                kind="exercise",
                                label="Problem 1",
                                block_id="b1",
                                page_number=1,
                            ),
                            Problem(
                                id="ch-1-p-2",
                                kind="exercise",
                                label="Problem 2",
                                block_id="b2",
                                page_number=2,
                            ),
                        ],
                    )
                ],
            ),
            Chapter(
                id="ch-2",
                number=2,
                title="Chapter 2",
                concepts=[
                    Concept(
                        id="ch-2-c-a",
                        title="Concept B",
                        problems=[
                            Problem(
                                id="ch-2-p-1",
                                kind="exercise",
                                label="Problem 1",
                                block_id="b3",
                                page_number=10,
                            )
                        ],
                    )
                ],
            ),
        ],
    )


def _engine() -> ProgressEngine:
    state = ProgressState(user_id="user-1", doc_id="doc-1", updated_at="2026-06-19T00:00:00+00:00")
    return ProgressEngine(syllabus=_syllabus(), state=state)


def test_set_focus_marks_in_progress() -> None:
    engine = _engine()
    engine.set_focus("ch-1-p-1")
    node = engine.state.nodes["ch-1-p-1"]
    assert node.status == "in_progress"
    assert engine.state.focus == FocusPointer(
        chapter_id="ch-1",
        concept_id="ch-1-c-a",
        problem_id="ch-1-p-1",
    )


def test_record_mastery_requires_both_flags() -> None:
    engine = _engine()
    engine.set_focus("ch-1-p-1")
    engine.record_mastery("ch-1-p-1", solved=True, explained=False)
    assert engine.state.nodes["ch-1-p-1"].status == "in_progress"
    assert engine.state.nodes["ch-1-p-1"].attempts == 1

    engine.record_mastery("ch-1-p-1", solved=True, explained=True)
    assert engine.state.nodes["ch-1-p-1"].status == "mastered"
    assert engine.state.next_suggestion == FocusPointer(
        chapter_id="ch-1",
        concept_id="ch-1-c-a",
        problem_id="ch-1-p-2",
    )


def test_next_suggestion_advances_across_chapters() -> None:
    engine = _engine()
    engine.record_mastery("ch-1-p-1", solved=True, explained=True)
    engine.record_mastery("ch-1-p-2", solved=True, explained=True)
    assert engine.state.next_suggestion == FocusPointer(
        chapter_id="ch-2",
        concept_id="ch-2-c-a",
        problem_id="ch-2-p-1",
    )
