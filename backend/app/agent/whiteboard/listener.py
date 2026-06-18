"""Wires the LiveKit data channel into a debounced ``BoardReader`` pipeline.

The agent worker calls :func:`install_user_board_listener` once per room. The
listener:

1. Registers a synchronous ``data_received`` handler that filters on the
   ``user_board`` topic and pushes the latest payload into a queue.
2. Runs a background task that waits for ``interval`` seconds of quiet on
   the queue, then drains it, picks the newest snapshot, and calls
   ``reader.interpret(png_bytes)``.
3. Stores the result on :class:`BoardState`.

``is_empty=True`` snapshots short-circuit the reader entirely.
"""

from __future__ import annotations

import asyncio
import base64
import logging
from dataclasses import dataclass
from typing import Any, Protocol

from .messages import USER_BOARD_TOPIC, UserBoardSnapshot
from .state import BoardState

logger = logging.getLogger("mathbird.agent.whiteboard.listener")


class _BoardReaderLike(Protocol):
    async def interpret(self, png_bytes: bytes) -> str: ...


class _RoomLike(Protocol):
    def on(self, event: str, handler: Any = None) -> Any:  # pyee-style
        ...


@dataclass
class UserBoardListenerHandle:
    task: asyncio.Task[None]

    async def aclose(self) -> None:
        self.task.cancel()
        try:
            await self.task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001 — defensive cleanup
            pass


def install_user_board_listener(
    *,
    room: _RoomLike,
    state: BoardState,
    reader: _BoardReaderLike,
    interval: float,
) -> UserBoardListenerHandle:
    """Install the data_received handler and start the debouncer task."""
    pending: asyncio.Queue[UserBoardSnapshot] = asyncio.Queue()

    def _on_data_received(packet: Any) -> None:  # duck-typed DataPacket
        if getattr(packet, "topic", None) != USER_BOARD_TOPIC:
            return
        try:
            snap = UserBoardSnapshot.model_validate_json(packet.data)
        except Exception:
            logger.exception("dropping malformed user_board payload")
            return
        pending.put_nowait(snap)

    room.on("data_received", _on_data_received)

    async def _debouncer() -> None:
        while True:
            snap = await pending.get()
            # Coalesce a burst — wait for a quiet window after the latest packet.
            while True:
                try:
                    snap = await asyncio.wait_for(pending.get(), timeout=interval)
                except TimeoutError:
                    break

            if snap.is_empty:
                state.record_empty(card_id=snap.card_id)
                continue

            try:
                png_bytes = base64.b64decode(snap.png_b64)
            except Exception:
                logger.exception("dropping snapshot with invalid base64")
                continue

            try:
                text = await reader.interpret(png_bytes)
            except Exception:
                logger.exception("board reader raised; leaving state untouched")
                continue

            if text.strip():
                state.record_reading(text, card_id=snap.card_id, card_label=snap.card_label)
            else:
                state.record_empty(card_id=snap.card_id)

    task = asyncio.create_task(_debouncer(), name="user_board_debouncer")
    return UserBoardListenerHandle(task=task)
