"""Server → clients publishing on the ``session_progress`` topic."""

from __future__ import annotations

from typing import Protocol

from app.progress.messages import SESSION_PROGRESS_TOPIC, SessionProgressUpdate


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


async def publish_session_progress(room: _RoomLike, update: SessionProgressUpdate) -> None:
    payload = update.model_dump_json().encode("utf-8")
    await room.local_participant.publish_data(
        payload,
        reliable=True,
        topic=SESSION_PROGRESS_TOPIC,
    )
