"""Server → clients publishing on the ``session_progress`` topic."""

from __future__ import annotations

from app.livekit.protocols import RoomLike
from app.progress.messages import SESSION_PROGRESS_TOPIC, SessionProgressUpdate


async def publish_session_progress(room: RoomLike, update: SessionProgressUpdate) -> None:
    payload = update.model_dump_json().encode("utf-8")
    await room.local_participant.publish_data(
        payload,
        reliable=True,
        topic=SESSION_PROGRESS_TOPIC,
    )
