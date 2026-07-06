"""Tests for ProgressEngine.apply_grade_result single-write path."""

from __future__ import annotations

from app.agent.grader.base import GradeResult, NodeUpdate
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
                        id="ch-1-c-expo",
                        title="Expository A",
                        block_ids=("b0",),
                    ),
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
            )
        ],
    )


def _engine() -> ProgressEngine:
    state = ProgressState(user_id="user-1", doc_id="doc-1", updated_at="2026-06-19T00:00:00+00:00")
    return ProgressEngine(syllabus=_syllabus(), state=state)


def test_apply_grade_result_sets_focus() -> None:
    engine = _engine()
    changed = engine.apply_grade_result(GradeResult(set_focus_node_id="ch-1-p-1"))
    assert changed is True
    assert engine.state.focus is not None
    assert engine.state.focus.problem_id == "ch-1-p-1"
    assert engine.effective_level("ch-1-p-1") == "practicing"


def test_apply_grade_result_mastery_advances_next_suggestion() -> None:
    engine = _engine()
    engine.apply_grade_result(GradeResult(set_focus_node_id="ch-1-p-1"))
    changed = engine.apply_grade_result(
        GradeResult(updates=[NodeUpdate(node_id="ch-1-p-1", level="mastered")])
    )
    assert changed is True
    assert engine.effective_level("ch-1-p-1") == "mastered"
    assert engine.state.nodes["ch-1-p-1"].attempts == 1
    assert engine.state.next_suggestion == FocusPointer(
        chapter_id="ch-1",
        concept_id="ch-1-c-a",
        problem_id="ch-1-p-2",
    )


def test_apply_grade_result_concept_mastery_advances_next_suggestion() -> None:
    engine = _engine()
    engine.apply_grade_result(GradeResult(set_focus_node_id="ch-1-c-expo"))
    changed = engine.apply_grade_result(
        GradeResult(updates=[NodeUpdate(node_id="ch-1-c-expo", level="mastered")])
    )
    assert changed is True
    assert engine.effective_level("ch-1-c-expo") == "mastered"
    assert engine.state.next_suggestion == FocusPointer(
        chapter_id="ch-1",
        concept_id="ch-1-c-a",
        problem_id="",
    )


def test_apply_grade_result_empty_returns_false() -> None:
    engine = _engine()
    assert engine.apply_grade_result(GradeResult()) is False
