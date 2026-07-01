"""Tests for ProgressEngine knowledge tracing."""

from __future__ import annotations

import pytest

from app.progress.engine import ProgressEngine, iter_problem_pointers
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
                    ),
                    # Concept with no problems but with content blocks — must
                    # still be trackable (a problem-poor expository section).
                    Concept(id="ch-1-c-b", title="Concept B", block_ids=("b9",)),
                ],
            ),
            Chapter(
                id="ch-2",
                number=2,
                title="Chapter 2",
                concepts=[
                    Concept(
                        id="ch-2-c-a",
                        title="Concept C",
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


def test_set_focus_marks_problem_practicing() -> None:
    engine = _engine()
    engine.set_focus("ch-1-p-1")
    node = engine.state.nodes["ch-1-p-1"]
    assert node.level == "practicing"
    assert engine.state.focus == FocusPointer(
        chapter_id="ch-1",
        concept_id="ch-1-c-a",
        problem_id="ch-1-p-1",
    )


def test_set_focus_on_concept_introduces_it() -> None:
    """A concept focus (no active problem) marks the concept as introduced."""
    engine = _engine()
    engine.set_focus("ch-1-c-b")  # concept with no problems
    assert engine.state.focus == FocusPointer(
        chapter_id="ch-1",
        concept_id="ch-1-c-b",
        problem_id="",
    )
    assert engine.state.nodes["ch-1-c-b"].level == "introduced"
    assert engine.effective_level("ch-1-c-b") == "introduced"


def test_record_mastery_requires_both_flags_for_mastered() -> None:
    engine = _engine()
    engine.set_focus("ch-1-p-1")
    engine.record_mastery("ch-1-p-1", solved=True, explained=False)
    # solved-only reaches proficient, not mastered.
    assert engine.state.nodes["ch-1-p-1"].level == "proficient"
    assert engine.state.nodes["ch-1-p-1"].attempts == 1

    engine.record_mastery("ch-1-p-1", solved=True, explained=True)
    assert engine.state.nodes["ch-1-p-1"].level == "mastered"
    assert engine.state.next_suggestion == FocusPointer(
        chapter_id="ch-1",
        concept_id="ch-1-c-a",
        problem_id="ch-1-p-2",
    )


def test_next_suggestion_advances_across_chapters() -> None:
    engine = _engine()
    engine.record_mastery("ch-1-p-1", solved=True, explained=True)
    engine.record_mastery("ch-1-p-2", solved=True, explained=True)
    # Both problems in ch-1-c-a mastered → the concept is mastered; the next
    # unmastered node is ch-1-c-b (an empty-problem concept), then ch-2-c-a.
    assert engine.state.next_suggestion == FocusPointer(
        chapter_id="ch-1",
        concept_id="ch-1-c-b",
        problem_id="",
    )


def test_set_level_is_monotonic_by_default() -> None:
    engine = _engine()
    engine.set_level("ch-1-p-1", "proficient")
    engine.set_level("ch-1-p-1", "practicing")  # lower — refused without force
    assert engine.state.nodes["ch-1-p-1"].level == "proficient"
    engine.set_level("ch-1-p-1", "practicing", force=True)
    assert engine.state.nodes["ch-1-p-1"].level == "practicing"


def test_set_level_marks_solved_and_explained_at_thresholds() -> None:
    engine = _engine()
    engine.set_level("ch-1-p-1", "proficient")
    assert engine.state.nodes["ch-1-p-1"].solved is True
    assert engine.state.nodes["ch-1-p-1"].explained is False
    engine.set_level("ch-1-p-1", "mastered")
    assert engine.state.nodes["ch-1-p-1"].explained is True


def test_effective_level_aggregates_concept_from_child_problems() -> None:
    engine = _engine()
    assert engine.effective_level("ch-1-c-a") == "not_started"
    engine.set_level("ch-1-p-1", "mastered")
    # ch-1-c-a has 2 problems; only one mastered → concept is proficient (not
    # mastered — the all-children gate isn't met).
    assert engine.effective_level("ch-1-c-a") == "proficient"
    # Mastering the second child lifts the concept to mastered.
    engine.set_level("ch-1-p-2", "mastered")
    assert engine.effective_level("ch-1-c-a") == "mastered"


def test_effective_level_concept_keeps_explicit_introduction() -> None:
    engine = _engine()
    engine.set_level("ch-1-c-a", "introduced")
    assert engine.effective_level("ch-1-c-a") == "introduced"


def test_record_misconception_and_clear() -> None:
    engine = _engine()
    engine.record_misconception("ch-1-p-1", "confused transpose with inverse")
    engine.record_misconception("ch-1-p-1", "confused transpose with inverse")  # dedup
    engine.record_misconception("ch-1-p-1", "sign error")
    assert engine.state.nodes["ch-1-p-1"].misconceptions == [
        "confused transpose with inverse",
        "sign error",
    ]
    engine.clear_misconceptions("ch-1-p-1")
    assert engine.state.nodes["ch-1-p-1"].misconceptions == []


def test_record_hint_increments() -> None:
    engine = _engine()
    engine.record_hint("ch-1-p-1")
    engine.record_hint("ch-1-p-1")
    assert engine.state.nodes["ch-1-p-1"].hints_given == 2


def test_set_focus_rejects_unknown_node() -> None:
    engine = _engine()
    with pytest.raises(ValueError):
        engine.set_focus("does-not-exist")


def test_summary_counts_ordinal_levels() -> None:
    engine = _engine()
    engine.set_level("ch-1-p-1", "mastered")
    engine.set_level("ch-1-p-2", "introduced")
    summary = engine.summary()
    # Trackable nodes = 3 concepts + 3 problems = 6.
    # ch-1-c-a has 2 problems: only p-1 mastered, p-2 introduced → concept is
    # proficient (all-children mastery gate not met). So:
    #   mastered: ch-1-p-1 only = 1.
    #   in_progress (>= introduced, < mastered): ch-1-c-a (proficient) + ch-1-p-2 = 2.
    assert summary.total == 6
    assert summary.mastered == 1
    assert summary.in_progress == 2


def test_snapshot_update_carries_full_level_and_concepts() -> None:
    """Phase D: the wire carries the full ordinal level + concept rows."""
    engine = _engine()
    engine.set_level("ch-1-p-1", "mastered")
    engine.set_level("ch-1-p-2", "proficient")
    snap = engine.snapshot_update()
    by_id = {n.problem_id: n for n in snap.nodes}
    assert by_id["ch-1-p-1"].status == "mastered"
    assert by_id["ch-1-p-2"].status == "proficient"  # full level, not collapsed
    assert by_id["ch-2-p-1"].status == "not_started"
    # Concept rows are present and reflect aggregated levels.
    concept_by_id = {c.concept_id: c for c in snap.concepts}
    assert "ch-1-c-a" in concept_by_id
    # ch-1-c-a has 2 problems: p-1 mastered, p-2 proficient → floor mastered,
    # but the all-children gate caps it at proficient.
    assert concept_by_id["ch-1-c-a"].level == "proficient"
    # A concept with no problems reports not_started until introduced.
    assert concept_by_id["ch-1-c-b"].level == "not_started"


# --------------------------------------------------------------- recommendations

def test_recommend_introduce_when_no_focus() -> None:
    engine = _engine()
    rec = engine.recommend()
    assert rec.intent == "introduce"
    # The first trackable node is the concept (concepts precede their problems).
    assert rec.focus_node_id == "ch-1-c-a"
    assert "Introduce" in rec.directive


def test_recommend_continue_at_default_focus() -> None:
    engine = _engine()
    engine.set_focus("ch-1-p-1")
    rec = engine.recommend()
    assert rec.intent == "continue"
    assert "ch-1-p-1" == rec.focus_node_id


def test_recommend_reinforce_at_proficient() -> None:
    engine = _engine()
    engine.set_focus("ch-1-p-1")
    engine.set_level("ch-1-p-1", "proficient")
    rec = engine.recommend()
    assert rec.intent == "reinforce"
    assert "explain" in rec.directive.lower()


def test_recommend_review_on_open_misconception() -> None:
    engine = _engine()
    engine.set_focus("ch-1-p-1")
    engine.record_misconception("ch-1-p-1", "sign error")
    rec = engine.recommend()
    assert rec.intent == "review"
    assert "sign error" in rec.directive


def test_recommend_review_when_stalled_with_hints() -> None:
    engine = _engine()
    engine.set_focus("ch-1-p-1")
    engine.record_hint("ch-1-p-1")
    engine.record_hint("ch-1-p-1")
    rec = engine.recommend()
    assert rec.intent == "review"
    assert "stuck" in rec.directive.lower() or "review" in rec.directive.lower()


def test_recommend_advance_after_mastery() -> None:
    engine = _engine()
    engine.set_focus("ch-1-p-1")
    engine.set_level("ch-1-p-1", "mastered")
    rec = engine.recommend()
    assert rec.intent == "advance"
    # Should point at the next problem.
    assert rec.focus_node_id == "ch-1-p-2"


def test_recommend_hold_when_all_mastered() -> None:
    engine = _engine()
    for _ptr, problem in iter_problem_pointers(engine.syllabus):
        engine.set_level(problem.id, "mastered")
    # Focus the last problem so _next_after returns None.
    engine.set_focus("ch-2-p-1")
    engine.set_level("ch-2-p-1", "mastered", force=True)
    rec = engine.recommend()
    assert rec.intent == "hold"


def test_format_injection_contains_next_action() -> None:
    engine = _engine()
    engine.set_focus("ch-1-p-1")
    injection = engine.format_injection()
    assert "[next action]" in injection
    assert "[session progress]" in injection


def test_format_injection_shows_anchor_when_no_focus() -> None:
    engine = _engine()
    injection = engine.format_injection()
    assert "(anchor:" in injection
    assert "ch-1-c-a" in injection  # first unmastered concept id in fixture

