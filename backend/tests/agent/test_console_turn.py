"""Tests for typed local turns invoking ``prepare_turn_context``."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from livekit.agents.voice.run_result import RunResult

from app.agent.console.turn import TurnRunResult, run_text_turn
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


@pytest.mark.asyncio
async def test_run_text_turn_runs_grader_before_llm(monkeypatch: pytest.MonkeyPatch) -> None:
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

    calls: list[str] = []

    async def _tracking_prepare(agent, turn_ctx, new_message):  # noqa: ANN001
        calls.append("prepare")
        from app.agent.turn_context.prepare import prepare_turn_context as real_prepare

        return await real_prepare(agent, turn_ctx, new_message)

    from app.agent.console import turn as turn_module

    monkeypatch.setattr(turn_module, "prepare_turn_context", _tracking_prepare)

    session = MagicMock()
    session._global_run_state = None
    handle = MagicMock()

    def _generate_reply(**kwargs):  # noqa: ANN003
        calls.append("reply")
        return handle

    session.generate_reply = _generate_reply

    result = await run_text_turn(session, agent, "almost nothing")

    assert calls == ["prepare", "reply"]
    assert isinstance(result, TurnRunResult)
    assert isinstance(result.run, RunResult)
    assert result.snapshot.injections
    await agent._pending_grader.drain()
    assert engine.state.focus is not None
    assert engine.state.focus.concept_id == "ch-1-c-a"
