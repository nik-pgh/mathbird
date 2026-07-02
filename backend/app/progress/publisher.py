"""Server → clients publishing on the ``session_progress`` topic."""

from __future__ import annotations

import logging

from app.livekit.protocols import RoomLike
from app.progress.messages import SESSION_PROGRESS_TOPIC, SessionProgressUpdate

logger = logging.getLogger("mathbird.progress.publisher")


async def publish_session_progress(room: RoomLike, update: SessionProgressUpdate) -> None:
    payload = update.model_dump_json().encode("utf-8")
    logger.info(
        "session_progress publish op=%s bytes=%d nodes=%d concepts=%d",
        update.op,
        len(payload),
        len(update.nodes),
        len(update.concepts),
    )
    await room.local_participant.publish_data(
        payload,
        reliable=True,
        topic=SESSION_PROGRESS_TOPIC,
    )
