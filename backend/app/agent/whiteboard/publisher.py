"""Server → clients publishing on the ``ai_board`` topic."""

from __future__ import annotations

from app.livekit.protocols import RoomLike

from .messages import AI_BOARD_TOPIC, AiBoardUpdate


async def publish_ai_board(room: RoomLike, update: AiBoardUpdate) -> None:
    """Serialize ``update`` and broadcast it on the ``ai_board`` topic."""
    payload = update.model_dump_json().encode("utf-8")
    await room.local_participant.publish_data(
        payload,
        reliable=True,
        topic=AI_BOARD_TOPIC,
    )
