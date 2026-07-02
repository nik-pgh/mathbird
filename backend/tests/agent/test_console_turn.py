"""Tests for typed local turns invoking ``prepare_turn_context``."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest
from livekit.agents.voice.run_result import RunResult

from app.agent.console.turn import TurnRunResult, await_turn_grading, run_text_turn
from app.agent.grader.base import GradeResult
from app.agent.grader.null import NullGrader
from app.agent.whiteboard.cache import BoardCache
from app.agent.whiteboard.state import BoardState
from app.agent.whiteboard_agent import WhiteboardAgent
from app.progress.engine import ProgressEngine
from app.progress.models import ProgressState
from app.syllabus.models import Chapter, Concept, Problem, Syllabus


def _engine() -> ProgressEngine:
    syllabus = Syllabus(
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
    state = ProgressState(user_id="user-1", doc_id="doc-1", updated_at="2026-06-19T00:00:00+00:00")
    return ProgressEngine(syllabus=syllabus, state=state)


class _FakeExtractor:
    async def extract(self, sentence, current_items, last_sentence):  # noqa: ANN001
        return []


class SlowGrader:
    """Blocks on ``release`` until the caller sets it."""

    def __init__(self, *, started: asyncio.Event, release: asyncio.Event) -> None:
        self._started = started
        self._release = release
        self.finished = False

    async def grade(self, **kwargs):  # noqa: ANN003
        self._started.set()
        await self._release.wait()
        self.finished = True
        return GradeResult()


@pytest.mark.asyncio
async def test_run_text_turn_starts_reply_before_grade_finishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAG_PROVIDER", "null")
    from app.config import get_settings

    get_settings.cache_clear()

    started = asyncio.Event()
    release = asyncio.Event()
    grader = SlowGrader(started=started, release=release)
    engine = _engine()
    agent = WhiteboardAgent(
        instructions="be a tutor",
        board_state=BoardState(),
        board_cache=BoardCache(),
        extractor=_FakeExtractor(),
        grader=grader,
        progress_engine=engine,
    )

    reply_started = False

    session = MagicMock()
    session._global_run_state = None
    handle = MagicMock()

    def _generate_reply(**kwargs):  # noqa: ANN003
        nonlocal reply_started
        reply_started = True
        return handle

    session.generate_reply = _generate_reply

    result = await run_text_turn(session, agent, "hello")

    await started.wait()
    assert reply_started
    assert isinstance(result, TurnRunResult)
    assert isinstance(result.run, RunResult)
    assert result.grading_task is not None
    assert not result.grading_task.done()
    assert not grader.finished

    release.set()
    await await_turn_grading(result)
    assert grader.finished


@pytest.mark.asyncio
async def test_await_turn_grading_applies_focus(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAG_PROVIDER", "null")
    from app.config import get_settings

    get_settings.cache_clear()

    engine = _engine()
    agent = WhiteboardAgent(
        instructions="be a tutor",
        board_state=BoardState(),
        board_cache=BoardCache(),
        extractor=_FakeExtractor(),
        grader=NullGrader(),
        progress_engine=engine,
    )

    session = MagicMock()
    session._global_run_state = None
    session.generate_reply = MagicMock(return_value=MagicMock())

    result = await run_text_turn(session, agent, "almost nothing")

    assert engine.state.focus is None
    assert result.grading_task is not None

    await await_turn_grading(result)

    assert engine.state.focus is not None
    assert engine.state.focus.concept_id == "ch-1-c-a"
