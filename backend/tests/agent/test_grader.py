"""Tests for the grader seam: Protocol, factory, and agent wiring."""

from __future__ import annotations

import pytest
from livekit.agents.llm import ChatContext, ChatMessage

from app.agent.grader import Grader, GradeResult, get_grader
from app.agent.grader.null import NullGrader
from app.agent.grader.openai import OpenAIGrader
from app.agent.whiteboard_agent import WhiteboardAgent
from app.config import get_settings
from app.progress.engine import ProgressEngine
from app.progress.models import ProgressState
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
                        ],
                    )
                ],
            )
        ],
    )


def _engine() -> ProgressEngine:
    state = ProgressState(user_id="user-1", doc_id="doc-1", updated_at="2026-06-19T00:00:00+00:00")
    return ProgressEngine(syllabus=_syllabus(), state=state)


# --------------------------------------------------------------------------- null

@pytest.mark.asyncio
async def test_null_grader_returns_empty() -> None:
    result = await NullGrader().grade(
        turn_text="I think x is 3",
        board_text="x + 2 = 5",
        focus_node_id="ch-1-p-1",
        levels={"ch-1-p-1": "practicing"},
        syllabus_context="Chapter 1 / Concept A / Problem 1",
        next_suggestion_node_id="ch-1-p-2",
    )
    assert result.updates == []
    assert result.set_focus_node_id is None


def test_default_factory_returns_null_grader(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GRADER", "null")
    get_settings.cache_clear()
    get_grader.cache_clear()
    settings = get_settings()
    assert settings.grader == "null"
    grader = get_grader()
    assert isinstance(grader, NullGrader)
    assert isinstance(grader, Grader)  # runtime_checkable Protocol


# --------------------------------------------------------------------------- openai

class _FakeMessage:
    def __init__(self, parsed) -> None:
        self.parsed = parsed


class _FakeChoice:
    def __init__(self, parsed) -> None:
        self.message = _FakeMessage(parsed)


class _FakeCompletion:
    def __init__(self, parsed) -> None:
        self.choices = [_FakeChoice(parsed)]


class _FakeCompletions:
    def __init__(self, parsed_factory) -> None:
        self._factory = parsed_factory

    async def parse(self, **kwargs):  # noqa: ANN003
        from app.agent.grader.openai import _GradedNode, _GradeResponse

        parsed = self._factory(_GradedNode, _GradeResponse)
        return _FakeCompletion(parsed)


class _FakeBeta:
    def __init__(self, parsed_factory) -> None:
        self.chat = type("C", (), {"completions": _FakeCompletions(parsed_factory)})()


class _FakeClient:
    def __init__(self, parsed_factory) -> None:
        self.beta = _FakeBeta(parsed_factory)


@pytest.mark.asyncio
async def test_openai_grader_applies_solved_update() -> None:
    """An OpenAI grader that returns a 'proficient' update advances the engine."""

    def factory(_GradedNode, _GradeResponse):
        return _GradeResponse(
            updates=[
                _GradedNode(
                    node_id="ch-1-p-1",
                    level="proficient",
                    note="student solved correctly but did not explain",
                )
            ]
        )

    grader = OpenAIGrader(model="test", timeout=5.0, client=_FakeClient(factory))
    engine = _engine()
    engine.set_focus("ch-1-p-1")
    assert engine.effective_level("ch-1-p-1") == "practicing"

    # Apply the full grader result via the ProgressEngine write path.
    result = await grader.grade(
        turn_text="I got x equals 3",
        board_text="x + 2 = 5",
        focus_node_id="ch-1-p-1",
        levels=engine.nearby_levels("ch-1-p-1"),
        syllabus_context=engine.focus_context("ch-1-p-1"),
    )
    assert len(result.updates) == 1
    changed = engine.apply_grade_result(result)
    assert changed is True
    assert engine.effective_level("ch-1-p-1") == "proficient"
    assert engine.state.nodes["ch-1-p-1"].solved is True


@pytest.mark.asyncio
async def test_openai_grader_skips_misconception_for_clarifying_question() -> None:
    """Clarifying questions about tutor wording must not record misconceptions.

    When a student asks what the tutor meant (e.g. "what do you mean by that?")
    rather than asserting incorrect math, the grader should emit no
    misconception_additions. The mocked response models correct grader behavior;
    the system prompt also instructs the model not to treat such turns as errors.
    """

    def factory(_GradedNode, _GradeResponse):
        return _GradeResponse(updates=[])

    grader = OpenAIGrader(model="test", timeout=5.0, client=_FakeClient(factory))
    engine = _engine()
    engine.set_focus("ch-1-p-1")

    result = await grader.grade(
        turn_text="what do you mean by that?",
        board_text=None,
        focus_node_id="ch-1-p-1",
        levels=engine.nearby_levels("ch-1-p-1"),
        syllabus_context=engine.focus_context("ch-1-p-1"),
        last_tutor_message="Remember to keep the terms in ordered form.",
    )
    engine.apply_grade_result(result)
    assert result.updates == []
    assert engine.state.nodes["ch-1-p-1"].misconceptions == []


def test_openai_grader_prompt_rejects_clarifying_question_misconceptions() -> None:
    """System prompt must tell the model not to grade clarifying questions as errors."""
    from app.agent.grader.openai import _SYSTEM_PROMPT

    assert (
        "Do NOT record misconceptions when the student asks clarifying questions"
        in _SYSTEM_PROMPT
    )


@pytest.mark.asyncio
async def test_openai_grader_records_misconception() -> None:

    def factory(_GradedNode, _GradeResponse):
        return _GradeResponse(
            updates=[
                _GradedNode(
                    node_id="ch-1-p-1",
                    misconception_additions=["sign error distributing the negative"],
                )
            ]
        )

    grader = OpenAIGrader(model="test", timeout=5.0, client=_FakeClient(factory))
    engine = _engine()
    engine.set_focus("ch-1-p-1")

    result = await grader.grade(
        turn_text="so x is negative 3",
        board_text="-(x+2)=5",
        focus_node_id="ch-1-p-1",
        levels=engine.nearby_levels("ch-1-p-1"),
        syllabus_context=engine.focus_context("ch-1-p-1"),
    )
    engine.apply_grade_result(result)
    assert engine.state.nodes["ch-1-p-1"].misconceptions == ["sign error distributing the negative"]


@pytest.mark.asyncio
async def test_openai_grader_returns_set_focus() -> None:
    def factory(_GradedNode, _GradeResponse):
        return _GradeResponse(set_focus_node_id="ch-1-c-a", updates=[])

    grader = OpenAIGrader(model="test", timeout=5.0, client=_FakeClient(factory))
    engine = _engine()
    engine.set_focus("ch-1-p-1")

    result = await grader.grade(
        turn_text="yes, let's do that next",
        board_text=None,
        focus_node_id="ch-1-p-1",
        levels=engine.nearby_levels("ch-1-p-1"),
        syllabus_context=engine.focus_context("ch-1-p-1"),
        next_suggestion_node_id="ch-1-c-a",
        next_suggestion_label="Concept A",
        recommend_intent="introduce",
        recommend_directive="move_to_next",
        last_tutor_message="Great work. Want to move to Concept A next?",
    )
    assert result.set_focus_node_id == "ch-1-c-a"


@pytest.mark.asyncio
async def test_openai_grader_returns_empty_on_exception() -> None:
    """A failing client must degrade to an empty GradeResult, never raise."""

    class _ExplodingCompletions:
        async def parse(self, **kwargs):  # noqa: ANN003
            raise RuntimeError("boom")

    class _ExplodingClient:
        def __init__(self) -> None:
            completions = _ExplodingCompletions()
            chat = type("C", (), {"completions": completions})()
            self.beta = type("B", (), {"chat": chat})()

    grader = OpenAIGrader(model="test", timeout=5.0, client=_ExplodingClient())
    result = await grader.grade(
        turn_text="anything",
        board_text=None,
        focus_node_id=None,
        levels={},
        syllabus_context="",
    )
    assert result.updates == []


# --------------------------------------------------------------------------- engine helpers

def test_nearby_levels_includes_focus_and_concept() -> None:
    engine = _engine()
    engine.set_focus("ch-1-p-1")
    levels = engine.nearby_levels("ch-1-p-1")
    assert "ch-1-p-1" in levels
    assert "ch-1-c-a" in levels


def test_focus_context_for_problem() -> None:
    engine = _engine()
    ctx = engine.focus_context("ch-1-p-1")
    assert "Chapter 1" in ctx
    assert "Concept A" in ctx
    assert "Problem 1" in ctx


@pytest.mark.asyncio
async def test_grade_turn_sets_focus_from_grader(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.agent.whiteboard.cache import BoardCache
    from app.agent.whiteboard.state import BoardState

    class _FakeExtractor:
        async def extract(self, sentence, current_items, last_sentence):  # noqa: ANN001
            return []

    class _FakeGrader:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        async def grade(self, **kwargs):  # noqa: ANN003
            self.calls.append(kwargs)
            return GradeResult(set_focus_node_id="ch-1-p-1")

    class _FakeSession:
        def __init__(self) -> None:
            self.history = ChatContext.empty()
            self.history.add_message(
                role="assistant",
                content="Great work. Want to move to Problem 1 next?",
            )

    async def _noop_persist(engine):  # noqa: ANN001
        return None

    monkeypatch.setattr("app.agent.turn_context.grade._persist_progress_via_store", _noop_persist)
    engine = _engine()
    grader = _FakeGrader()
    agent = WhiteboardAgent(
        instructions="be a tutor",
        board_state=BoardState(),
        board_cache=BoardCache(),
        extractor=_FakeExtractor(),
        grader=grader,
        progress_engine=engine,
    )
    agent._fake_session_for_tests = _FakeSession()  # type: ignore[attr-defined]

    from app.agent.turn_context.grade import grade_student_turn

    await grade_student_turn(agent, ChatMessage(role="user", content=["yes, let's do that next"]))

    assert engine.state.focus is not None
    assert engine.state.focus.problem_id == "ch-1-p-1"
    assert len(grader.calls) == 1
    assert grader.calls[0]["recommend_intent"] == "introduce"
    assert grader.calls[0]["next_suggestion_node_id"] == "ch-1-c-a"
    assert grader.calls[0]["next_suggestion_label"] == "Concept A"
    assert grader.calls[0]["last_tutor_message"] == "Great work. Want to move to Problem 1 next?"


@pytest.mark.asyncio
async def test_grade_turn_engine_fallback_when_grader_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Introduce engagement anchors focus even when the grader returns no-op."""
    from app.agent.whiteboard.cache import BoardCache
    from app.agent.whiteboard.state import BoardState

    class _FakeExtractor:
        async def extract(self, sentence, current_items, last_sentence):  # noqa: ANN001
            return []

    class _FakeSession:
        def __init__(self) -> None:
            self.history = ChatContext()

    async def _noop_persist(engine):  # noqa: ANN001
        return None

    monkeypatch.setattr("app.agent.turn_context.grade._persist_progress_via_store", _noop_persist)
    engine = _engine()
    agent = WhiteboardAgent(
        instructions="be a tutor",
        board_state=BoardState(),
        board_cache=BoardCache(),
        extractor=_FakeExtractor(),
        grader=NullGrader(),
        progress_engine=engine,
    )
    agent._fake_session_for_tests = _FakeSession()  # type: ignore[attr-defined]

    from app.agent.turn_context.grade import grade_student_turn

    await grade_student_turn(agent, ChatMessage(role="user", content=["almost nothing"]))

    assert engine.state.focus is not None
    assert engine.state.focus.concept_id == "ch-1-c-a"
    assert engine.effective_level("ch-1-c-a") == "introduced"
