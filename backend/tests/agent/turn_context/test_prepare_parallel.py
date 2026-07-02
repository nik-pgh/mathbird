"""Tests for parallel grader scheduling in prepare_turn_context."""

from __future__ import annotations

import asyncio

import pytest
from livekit.agents.llm import ChatContext, ChatMessage

from app.agent.grader.base import GradeResult
from app.agent.turn_context.prepare import prepare_turn_context
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


def _agent(grader: SlowGrader, engine: ProgressEngine | None = None) -> WhiteboardAgent:
    return WhiteboardAgent(
        instructions="be a tutor",
        board_state=BoardState(),
        board_cache=BoardCache(),
        extractor=_FakeExtractor(),
        grader=grader,
        progress_engine=engine if engine is not None else _engine(),
    )


@pytest.mark.asyncio
async def test_prepare_returns_before_grade_finishes() -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    grader = SlowGrader(started=started, release=release)
    agent = _agent(grader)
    turn_ctx = ChatContext.empty()
    message = ChatMessage(role="user", content=["hello"])

    prepared = await prepare_turn_context(agent, turn_ctx, message)

    await started.wait()
    assert prepared.grading_task is not None
    assert not prepared.grading_task.done()
    assert not grader.finished

    release.set()
    await agent._pending_grader.drain()
    assert grader.finished


@pytest.mark.asyncio
async def test_turn_n_inject_waits_for_turn_n_minus_1_grade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order: list[str] = []

    release_turn_1 = asyncio.Event()
    started_turn_1 = asyncio.Event()

    class _TrackingSlowGrader(SlowGrader):
        def __init__(self) -> None:
            super().__init__(started=started_turn_1, release=release_turn_1)
            self._call = 0

        async def grade(self, **kwargs):  # noqa: ANN003
            self._call += 1
            if self._call == 1:
                order.append("grade_1_start")
                await super().grade(**kwargs)
                order.append("grade_1_done")
            else:
                order.append("grade_2_done")
                return GradeResult()
            return GradeResult()

    original_base_injections = None

    def _tracking_base_injections(self):  # noqa: ANN001
        order.append(f"inject_{len([e for e in order if e.startswith('inject_')]) + 1}")
        return original_base_injections(self)

    from app.agent.turn_context import builder as builder_module

    original_base_injections = builder_module.TurnContextBuilder.base_injections
    monkeypatch.setattr(
        builder_module.TurnContextBuilder,
        "base_injections",
        _tracking_base_injections,
    )

    grader = _TrackingSlowGrader()
    agent = _agent(grader)
    turn_ctx_1 = ChatContext.empty()
    turn_ctx_2 = ChatContext.empty()

    prepared_1 = await prepare_turn_context(
        agent,
        turn_ctx_1,
        ChatMessage(role="user", content=["turn one"]),
    )
    await started_turn_1.wait()
    assert prepared_1.grading_task is not None
    assert not prepared_1.grading_task.done()

    turn_2_done = asyncio.Event()

    async def run_turn_2() -> None:
        await prepare_turn_context(
            agent,
            turn_ctx_2,
            ChatMessage(role="user", content=["turn two"]),
        )
        turn_2_done.set()

    turn_2_task = asyncio.create_task(run_turn_2())
    await asyncio.sleep(0)
    assert not turn_2_done.is_set()

    release_turn_1.set()
    await turn_2_task

    assert order == [
        "inject_1",
        "grade_1_start",
        "grade_1_done",
        "inject_2",
        "grade_2_done",
    ]
