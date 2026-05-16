"""Behavior tests for the debounced user-board listener.

The listener wires ``room.on("data_received")`` (LiveKit's pyee-style event
emitter) into an asyncio queue + debouncer task that calls the reader and
mutates ``BoardState``. We fake just enough of the LiveKit surface to drive
it.
"""

from __future__ import annotations

import asyncio
import base64
from collections.abc import Callable
from dataclasses import dataclass, field

from app.agent.whiteboard.listener import install_user_board_listener
from app.agent.whiteboard.messages import USER_BOARD_TOPIC, UserBoardSnapshot
from app.agent.whiteboard.state import BoardState


@dataclass
class _FakeDataPacket:
    data: bytes
    topic: str | None
    participant: object | None = None


@dataclass
class _FakeRoom:
    handlers: dict[str, list[Callable]] = field(default_factory=dict)

    def on(self, event: str, handler: Callable | None = None):
        if handler is None:
            def _decorator(h: Callable) -> Callable:
                self.handlers.setdefault(event, []).append(h)
                return h

            return _decorator
        self.handlers.setdefault(event, []).append(handler)
        return handler

    def emit(self, event: str, *args: object) -> None:
        for h in self.handlers.get(event, []):
            h(*args)


class _RecordingReader:
    def __init__(self, response: str = "interpreted") -> None:
        self.response = response
        self.calls: list[bytes] = []

    async def interpret(self, png_bytes: bytes) -> str:
        self.calls.append(png_bytes)
        return self.response


def _snapshot(payload: bytes = b"png-bytes-here", *, is_empty: bool = False) -> bytes:
    snap = UserBoardSnapshot(
        png_b64=base64.b64encode(payload).decode("ascii"),
        captured_at_ms=1700000000000,
        is_empty=is_empty,
    )
    return snap.model_dump_json().encode("utf-8")


async def test_listener_debounces_bursts_into_one_interpret_call() -> None:
    room = _FakeRoom()
    state = BoardState()
    reader = _RecordingReader("x = 3")

    handle = install_user_board_listener(room=room, state=state, reader=reader, interval=0.05)
    try:
        # Three packets in quick succession should collapse into one call.
        for _ in range(3):
            room.emit("data_received", _FakeDataPacket(data=_snapshot(), topic=USER_BOARD_TOPIC))
            await asyncio.sleep(0)  # yield to the loop without arming the debounce
        # Wait for the debounce window to expire + a little slack.
        await asyncio.sleep(0.15)

        assert len(reader.calls) == 1
        assert state.user_text == "x = 3"
        assert state.is_blank is False
    finally:
        await handle.aclose()


async def test_listener_ignores_other_topics() -> None:
    room = _FakeRoom()
    state = BoardState()
    reader = _RecordingReader("should not be called")

    handle = install_user_board_listener(room=room, state=state, reader=reader, interval=0.05)
    try:
        room.emit("data_received", _FakeDataPacket(data=b"{}", topic="something_else"))
        await asyncio.sleep(0.15)

        assert reader.calls == []
        assert state.user_text == ""
    finally:
        await handle.aclose()


async def test_listener_handles_is_empty_without_calling_reader() -> None:
    room = _FakeRoom()
    state = BoardState()
    state.record_reading("stale")
    reader = _RecordingReader("should not be called")

    handle = install_user_board_listener(room=room, state=state, reader=reader, interval=0.05)
    try:
        room.emit(
            "data_received",
            _FakeDataPacket(data=_snapshot(is_empty=True), topic=USER_BOARD_TOPIC),
        )
        await asyncio.sleep(0.15)

        assert reader.calls == []
        assert state.user_text == ""
        assert state.is_blank is True
    finally:
        await handle.aclose()


async def test_listener_swallows_malformed_payloads() -> None:
    room = _FakeRoom()
    state = BoardState()
    reader = _RecordingReader("ignored")

    handle = install_user_board_listener(room=room, state=state, reader=reader, interval=0.05)
    try:
        room.emit(
            "data_received",
            _FakeDataPacket(data=b"not-json-at-all", topic=USER_BOARD_TOPIC),
        )
        await asyncio.sleep(0.15)

        assert reader.calls == []
        assert state.user_text == ""
    finally:
        await handle.aclose()
