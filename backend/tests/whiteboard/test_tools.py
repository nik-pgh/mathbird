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
    """

    userdata: BoardState
    room_io: _FakeRoomIO


@dataclass
class _FakeRunContext:
    session: _FakeSession


def _ctx(state: BoardState | None = None) -> _FakeRunContext:
    state = state if state is not None else BoardState()
    room = _FakeRoom()
    return _FakeRunContext(session=_FakeSession(userdata=state, room_io=_FakeRoomIO(room=room)))


def test_build_function_tools_includes_whiteboard_tools() -> None:
    tools = build_function_tools()
    names = {t.__name__ for t in tools}  # type: ignore[attr-defined]
    assert {"search_documents", "update_ai_board", "clear_ai_board", "read_user_board"} <= names


async def test_update_ai_board_publishes_upsert() -> None:
    ctx = _ctx()
    result = await update_ai_board(ctx, items=[AiBoardText(id="t1", markdown="hi")])
    assert "1" in result  # ack mentions the item count

    calls = ctx.session.room_io.room.local_participant.calls
    assert len(calls) == 1
    assert calls[0].topic == AI_BOARD_TOPIC
    decoded = json.loads(calls[0].payload.decode("utf-8"))
    assert decoded["op"] == "upsert"
    assert decoded["items"][0]["id"] == "t1"


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
