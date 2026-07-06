"""Tests for per-turn textbook excerpt prefetch and cache re-injection."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from livekit.agents.llm import ChatContext, ChatMessage

from app.agent.turn_context.prepare import prepare_turn_context
from app.agent.whiteboard import BoardCache, BoardState, SessionData
from app.agent.whiteboard_agent import WhiteboardAgent
from app.config import get_settings
from app.progress.engine import ProgressEngine
from app.progress.models import ProgressState
from app.rag.retriever import RetrievedChunk
from app.syllabus.models import Chapter, Concept, Problem, Syllabus


@dataclass
class _CountingRetriever:
    calls: int = 0

    async def retrieve(self, query: str, *, top_k: int = 4, doc_ids: tuple[str, ...] = ()):
        self.calls += 1
        return [
            RetrievedChunk(
                text=f"chunk for {query}",
                source="book.pdf, page 1",
            )
        ]


class _FakeExtractor:
    async def extract(self, sentence, current_items, last_sentence):  # noqa: ANN001
        return []


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
                        title="Linear Algebra",
                        block_ids=("b1",),
                        problems=[
                            Problem(
                                id="ch-1-p-1",
                                kind="exercise",
                                label="Problem 1",
                                block_id="b2",
                                page_number=1,
                            )
                        ],
                    )
                ],
            )
        ],
    )


def _agent(retriever: _CountingRetriever) -> WhiteboardAgent:
    state = ProgressState(user_id="u1", doc_id="doc-1", updated_at="2026-06-19T00:00:00+00:00")
    engine = ProgressEngine(syllabus=_syllabus(), state=state)
    engine.set_focus("ch-1-c-a")
    board_state = BoardState()
    session_data = SessionData(
        board_state=board_state,
        board_cache=BoardCache(),
        active_doc_id="doc-1",
        user_id="u1",
        syllabus=_syllabus(),
        progress_engine=engine,
    )
    agent = WhiteboardAgent(
        instructions="tutor",
        board_state=board_state,
        board_cache=BoardCache(),
        extractor=_FakeExtractor(),
        progress_engine=engine,
    )
    agent._fake_session_for_tests = type(  # type: ignore[attr-defined]
        "S", (), {"userdata": session_data}
    )()
    agent._counting_retriever = retriever  # type: ignore[attr-defined]
    return agent


def _textbook_blocks(turn_ctx: ChatContext) -> list[str]:
    blocks: list[str] = []
    for item in turn_ctx.items:
        if item.type != "message" or item.role != "system":
            continue
        text = item.text_content
        if text and text.startswith("[textbook excerpt]"):
            blocks.append(text)
    return blocks


@pytest.mark.asyncio
async def test_focus_change_reinjects_cached_excerpt_without_refetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAG_PROVIDER", "llamaindex_qdrant")
    monkeypatch.setenv("RAG_PREFETCH_MODE", "focus_change")
    get_settings.cache_clear()

    retriever = _CountingRetriever()
    monkeypatch.setattr(
        "app.agent.whiteboard_agent.get_retriever",
        lambda: retriever,
    )
    agent = _agent(retriever)

    for _ in range(2):
        turn_ctx = ChatContext.empty()
        await prepare_turn_context(agent, turn_ctx, ChatMessage(role="user", content=["hi"]))

    assert retriever.calls == 1
    turn_ctx = ChatContext.empty()
    await prepare_turn_context(agent, turn_ctx, ChatMessage(role="user", content=["again"]))
    assert retriever.calls == 1
    assert len(_textbook_blocks(turn_ctx)) == 1
    assert "Coarse preview" in _textbook_blocks(turn_ctx)[0]
    assert "search_documents" in _textbook_blocks(turn_ctx)[0]


@pytest.mark.asyncio
async def test_always_mode_refetches_each_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAG_PROVIDER", "llamaindex_qdrant")
    monkeypatch.setenv("RAG_PREFETCH_MODE", "always")
    get_settings.cache_clear()

    retriever = _CountingRetriever()
    monkeypatch.setattr(
        "app.agent.whiteboard_agent.get_retriever",
        lambda: retriever,
    )
    agent = _agent(retriever)

    for _ in range(2):
        turn_ctx = ChatContext.empty()
        await prepare_turn_context(agent, turn_ctx, ChatMessage(role="user", content=["hi"]))

    assert retriever.calls == 2
    assert len(_textbook_blocks(turn_ctx)) == 1
