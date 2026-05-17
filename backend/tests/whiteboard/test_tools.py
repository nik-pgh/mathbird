import json
from dataclasses import dataclass, field

from app.agent.tools import (
    build_function_tools,
    clear_ai_board,
    read_user_board,
    update_ai_board,
)
from app.agent.whiteboard.messages import AI_BOARD_TOPIC, AiBoardText
from app.agent.whiteboard.state import BoardState


@dataclass
class _Call:
    payload: bytes | str
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
    """Minimal stand-in for ``livekit.agents.AgentSession``.

    The tools touch only ``session.userdata`` and ``session.room_io.room``.
    ``userdata`` is either a ``SessionData`` (new shape) or a bare
    ``BoardState`` (legacy shape — kept working defensively).
    """

    userdata: object
    room_io: _FakeRoomIO


@dataclass
class _FakeRunContext:
    session: _FakeSession


def _ctx(state: BoardState | None = None) -> _FakeRunContext:
    state = state if state is not None else BoardState()
    room = _FakeRoom()
    from app.agent.whiteboard import BoardCache, SessionData

    data = SessionData(board_state=state, board_cache=BoardCache())
    return _FakeRunContext(session=_FakeSession(userdata=data, room_io=_FakeRoomIO(room=room)))


def test_build_function_tools_exposes_only_search_and_read() -> None:
    # AiBoard writes are owned by the extractor now; update_ai_board and
    # clear_ai_board are NOT in the LLM-facing tool list.
    tools = build_function_tools()
    names = {t.__name__ for t in tools}  # type: ignore[attr-defined]
    assert names == {"search_documents", "read_user_board"}


async def test_update_ai_board_publishes_upsert() -> None:
    ctx = _ctx()
    result = await update_ai_board(ctx, items=[AiBoardText(kind="text", id="t1", markdown="hi")])
    assert "1" in result  # ack mentions the item count

    calls = ctx.session.room_io.room.local_participant.calls
    assert len(calls) == 1
    assert calls[0].topic == AI_BOARD_TOPIC
    decoded = json.loads(calls[0].payload.decode("utf-8"))
    assert decoded["op"] == "upsert"
    assert decoded["items"][0]["id"] == "t1"


async def test_update_ai_board_returns_corrective_error_when_publish_fails(
    monkeypatch,
) -> None:
    # Regression: livekit's function-tool layer turns uncaught exceptions
    # into the literal string "An internal error occurred", which gives the
    # LLM no actionable signal to retry. The tool must catch and return the
    # concrete error so the LLM can self-correct.
    import app.agent.tools as tools

    async def boom(*_args, **_kwargs):
        raise RuntimeError("publish blew up")

    monkeypatch.setattr(tools, "publish_ai_board", boom)

    ctx = _ctx()
    result = await update_ai_board(ctx, items=[AiBoardText(kind="text", id="t1", markdown="hi")])
    assert "update_ai_board failed" in result
    assert "RuntimeError" in result
    assert "publish blew up" in result


async def test_clear_ai_board_publishes_clear() -> None:
    ctx = _ctx()
    await clear_ai_board(ctx)
    calls = ctx.session.room_io.room.local_participant.calls
    decoded = json.loads(calls[0].payload.decode("utf-8"))
    assert decoded == {"op": "clear", "items": []}


async def test_read_user_board_returns_state_text() -> None:
    state = BoardState()
    state.record_reading("2x = 6")
    ctx = _ctx(state)
    out = await read_user_board(ctx)
    assert "2x = 6" in out


async def test_read_user_board_when_blank_says_so() -> None:
    ctx = _ctx()
    out = await read_user_board(ctx)
    assert "blank" in out.lower() or "empty" in out.lower() or "no reading" in out.lower()
