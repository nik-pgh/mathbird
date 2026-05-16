import json
from dataclasses import dataclass, field

from app.agent.whiteboard.messages import (
    AI_BOARD_TOPIC,
    AiBoardText,
    AiBoardUpdate,
)
from app.agent.whiteboard.publisher import publish_ai_board


@dataclass
class _Call:
    payload: bytes | str
    topic: str
    reliable: bool


@dataclass
class _FakeLocalParticipant:
    calls: list[_Call] = field(default_factory=list)

    async def publish_data(self, payload, *, reliable=True, topic="", destination_identities=None):  # noqa: ANN001, ARG002
        self.calls.append(_Call(payload=payload, topic=topic, reliable=reliable))


@dataclass
class _FakeRoom:
    local_participant: _FakeLocalParticipant = field(default_factory=_FakeLocalParticipant)


async def test_publish_ai_board_sends_json_on_ai_board_topic() -> None:
    room = _FakeRoom()
    update = AiBoardUpdate(op="upsert", items=[AiBoardText(id="t1", markdown="hi")])

    await publish_ai_board(room, update)

    assert len(room.local_participant.calls) == 1
    call = room.local_participant.calls[0]
    assert call.topic == AI_BOARD_TOPIC
    assert call.reliable is True
    assert isinstance(call.payload, bytes)
    decoded = json.loads(call.payload.decode("utf-8"))
    assert decoded == {
        "op": "upsert",
        "items": [{"kind": "text", "id": "t1", "markdown": "hi"}],
    }


async def test_publish_ai_board_clear_sends_empty_items() -> None:
    room = _FakeRoom()
    await publish_ai_board(room, AiBoardUpdate(op="clear"))

    call = room.local_participant.calls[0]
    decoded = json.loads(call.payload.decode("utf-8"))
    assert decoded == {"op": "clear", "items": []}
