"""Duck-typed LiveKit room/participant shapes for data-channel publishers."""

from __future__ import annotations

from typing import Protocol


class LocalParticipantLike(Protocol):
    async def publish_data(
        self,
        payload: bytes | str,
        *,
        reliable: bool = True,
        destination_identities: list[str] = ...,
        topic: str = ...,
    ) -> None: ...


class RoomLike(Protocol):
    @property
    def local_participant(self) -> LocalParticipantLike: ...
