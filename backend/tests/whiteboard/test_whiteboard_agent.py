"""``WhiteboardAgent`` does three things:

1. Injects the latest user-board reading into the per-turn ChatContext.
2. Overrides ``transcription_node`` to tee text segments — pass them to
   TTS unchanged AND feed a sentence buffer for the extractor worker.
3. Runs a single background extractor worker, started in ``on_enter`` and
   cancelled in ``on_exit``, that pulls sentences and publishes
   ``update_ai_board`` items per sentence.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field

from livekit.agents import Agent
from livekit.agents.llm import ChatContext, ChatMessage

from app.agent.whiteboard import BoardCache, BoardState, SessionData
from app.agent.whiteboard.messages import AI_BOARD_TOPIC, AiBoardItem, AiBoardText
from app.agent.whiteboard_agent import WhiteboardAgent


def _user_message(text: str) -> ChatMessage:
    return ChatMessage(role="user", content=[text])


def _body(message) -> str:
    content = message.content
    return content[0] if isinstance(content, list) else content


# ── Fakes ───────────────────────────────────────────────────────────────


@dataclass
class _Call:
    payload: bytes
    topic: str


@dataclass
class _FakeLocalParticipant:
    calls: list[_Call] = field(default_factory=list)

    async def publish_data(self, payload, *, reliable=True, topic="", destination_identities=None):  # noqa: ANN001, ARG002
        self.calls.append(_Call(payload=payload, topic=topic))


@dataclass
class _FakeRoom:
    local_participant: _FakeLocalParticipant = field(default_factory=_FakeLocalParticipant)


@dataclass
class _FakeRoomIO:
    room: _FakeRoom


@dataclass
class _FakeSession:
    userdata: SessionData
    room_io: _FakeRoomIO


class _StubExtractor:
    """Returns canned items per ``sentence`` argument; remembers calls."""

    def __init__(self, responses: dict[str, list[AiBoardItem]]):
        self._responses = responses
        self.calls: list[tuple[str, list[AiBoardItem], str | None]] = []

    async def extract(self, sentence, current_items, last_sentence):
        self.calls.append((sentence, list(current_items), last_sentence))
        return list(self._responses.get(sentence, []))


def _make_agent(extractor=None) -> tuple[WhiteboardAgent, SessionData, _FakeSession]:
    state = BoardState()
    cache = BoardCache()
    data = SessionData(board_state=state, board_cache=cache)
    session = _FakeSession(userdata=data, room_io=_FakeRoomIO(room=_FakeRoom()))
    extractor = extractor if extractor is not None else _StubExtractor({})
    agent = WhiteboardAgent(
        instructions="be a tutor",
        board_state=state,
        board_cache=cache,
        extractor=extractor,
    )
    # Manually bind a fake session reference. The Agent base class normally
    # binds this when added to AgentSession; for unit tests we set it
    # directly so on_enter/transcription_node can read self.session.
    agent._fake_session_for_tests = session  # type: ignore[attr-defined]
    return agent, data, session


# ── on_user_turn_completed — user-board reading injection ──────────────


async def test_no_user_reading_still_injects_tutor_board() -> None:
    agent, _, _ = _make_agent()
    ctx = ChatContext.empty()
    await agent.on_user_turn_completed(ctx, _user_message("help"))
    assert len(ctx.items) == 1
    assert _body(ctx.items[0]).startswith("[tutor board]")


async def test_reading_is_injected_as_system_message() -> None:
    agent, data, _ = _make_agent()
    data.board_state.user_text = "2x + 3 = 9"
    data.board_state.is_blank = False
    data.board_state.refreshed_at = time.time() - 1.0
    ctx = ChatContext.empty()

    await agent.on_user_turn_completed(ctx, _user_message("what should I do?"))

    assert len(ctx.items) == 2
    body = _body(ctx.items[0])
    assert "user whiteboard" in body.lower()
    assert "2x + 3 = 9" in body
    assert _body(ctx.items[1]).startswith("[tutor board]")


async def test_blank_board_emits_status_line() -> None:
    agent, data, _ = _make_agent()
    data.board_state.record_empty()
    ctx = ChatContext.empty()

    await agent.on_user_turn_completed(ctx, _user_message("ok"))

    assert len(ctx.items) == 2
    body = _body(ctx.items[0])
    assert "blank" in body.lower() or "empty" in body.lower()
    assert _body(ctx.items[1]).startswith("[tutor board]")


# ── transcription_node — text passes through; sentences feed worker ────


async def test_transcription_node_passes_text_through_unchanged() -> None:
    agent, _, _ = _make_agent()

    async def fake_input():
        for chunk in ["Hello ", "world. "]:
            yield chunk

    output = []
    async for chunk in agent.transcription_node(fake_input(), model_settings=None):
        output.append(chunk)

    assert "".join(output) == "Hello world. "


async def test_tts_node_speaks_math_without_mutating_transcription_text(monkeypatch) -> None:
    agent, _, _ = _make_agent()

    async def fake_parent_tts_node(self, text, model_settings):  # noqa: ANN001, ARG001
        async for chunk in text:
            yield chunk

    monkeypatch.setattr(Agent, "tts_node", fake_parent_tts_node)

    async def fake_input():
        for chunk in ["Now $x", "^2 + 1 = 5$. "]:
            yield chunk

    output = []
    async for chunk in agent.tts_node(fake_input(), model_settings=None):
        output.append(chunk)

    assert output == ["Now x squared plus 1 equals 5. "]


async def test_extractor_called_on_sentence_boundary() -> None:
    stub = _StubExtractor(
        {
            "Let's set up 2x + 5 = 10.": [
                AiBoardText(kind="text", id="eq1", markdown="$2x + 5 = 10$")
            ]
        }
    )
    agent, _, _ = _make_agent(extractor=stub)

    await agent.on_enter()

    async def fake_input():
        for chunk in ["Let's set up 2x + 5 = 10. ", "What's next? "]:
            yield chunk

    async for _ in agent.transcription_node(fake_input(), model_settings=None):
        pass

    # Give the worker a moment to drain
    await asyncio.sleep(0.05)
    await agent.on_exit()

    # Stub saw both sentences (the second produced no items)
    sentences = [c[0] for c in stub.calls]
    assert "Let's set up 2x + 5 = 10." in sentences
    assert "What's next?" in sentences


async def test_extractor_items_are_published_and_cached() -> None:
    stub = _StubExtractor(
        {
            "Let's set up 2x + 5 = 10.": [
                AiBoardText(kind="text", id="eq1", markdown="$2x + 5 = 10$")
            ]
        }
    )
    agent, data, session = _make_agent(extractor=stub)
    await agent.on_enter()

    async def fake_input():
        yield "Let's set up 2x + 5 = 10. "

    async for _ in agent.transcription_node(fake_input(), model_settings=None):
        pass

    await asyncio.sleep(0.05)
    await agent.on_exit()

    # Published over the data channel
    calls = session.room_io.room.local_participant.calls
    assert len(calls) == 1
    assert calls[0].topic == AI_BOARD_TOPIC
    payload = json.loads(calls[0].payload.decode("utf-8"))
    assert payload["op"] == "upsert"
    assert payload["items"][0]["id"] == "eq1"

    # Cached
    assert len(data.board_cache.current_items()) == 1
    assert data.board_cache.current_items()[0].id == "eq1"


async def test_last_sentence_passed_to_next_extract_call() -> None:
    stub = _StubExtractor({})
    agent, _, _ = _make_agent(extractor=stub)
    await agent.on_enter()

    async def fake_input():
        yield "First sentence. Second sentence. "

    async for _ in agent.transcription_node(fake_input(), model_settings=None):
        pass

    await asyncio.sleep(0.05)
    await agent.on_exit()

    # First call: last_sentence is None. Second call: last_sentence is the first.
    assert stub.calls[0][2] is None
    assert stub.calls[1][2] == "First sentence."
