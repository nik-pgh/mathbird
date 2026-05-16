"""Server → clients publishing on the ``ai_board`` topic."""

from __future__ import annotations

from typing import Protocol

from .messages import AI_BOARD_TOPIC, AiBoardUpdate


class _LocalParticipantLike(Protocol):
    async def publish_data(
        self,
        payload: bytes | str,
        *,
        reliable: bool = True,
        destination_identities: list[str] = ...,
        topic: str = ...,
    ) -> None: ...


class _RoomLike(Protocol):
    @property
    def local_participant(self) -> _LocalParticipantLike: ...


async def publish_ai_board(room: _RoomLike, update: AiBoardUpdate) -> None:
    """Serialize ``update`` and broadcast it on the ``ai_board`` topic."""
    payload = update.model_dump_json().encode("utf-8")
    await room.local_participant.publish_data(
        payload,
        reliable=True,
        topic=AI_BOARD_TOPIC,
    )
