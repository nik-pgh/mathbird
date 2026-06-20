"""Tests for session progress publisher."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.progress.engine import ProgressEngine
from app.progress.messages import SESSION_PROGRESS_TOPIC
from app.progress.models import ProgressState
from app.progress.publisher import publish_session_progress
from app.syllabus.models import Chapter, Concept, Problem, Syllabus


@dataclass
class _Call:
    payload: bytes
    topic: str


@dataclass
class _FakeLocalParticipant:
    calls: list[_Call] = field(default_factory=list)

    async def publish_data(self, payload, *, reliable=True, topic="", destination_identities=None):  # noqa: ANN001, ARG002
        self.calls.append(_Call(payload=payload, topic=topic))


@dataclass
class _FakeRoom:
    local_participant: _FakeLocalParticipant = field(default_factory=_FakeLocalParticipant)


def _engine() -> ProgressEngine:
    syllabus = Syllabus(
        doc_id="doc-1",
        built_at="t",
        chapters=[
            Chapter(
                id="ch-1",
                number=1,
                title="Chapter 1",
                concepts=[
                    Concept(
                        id="ch-1-c-a",
                        title="A",
                        problems=[
                            Problem(
                                id="ch-1-p-1",
                                kind="exercise",
                                label="Problem 1",
                                block_id="b1",
                                page_number=1,
                            )
                        ],
                    )
                ],
            )
        ],
    )
    state = ProgressState(user_id="u1", doc_id="doc-1", updated_at="t")
    return ProgressEngine(syllabus=syllabus, state=state)


@pytest.mark.asyncio
async def test_publish_session_progress_encodes_snapshot() -> None:
    room = _FakeRoom()
    await publish_session_progress(room, _engine().snapshot_update())

    assert len(room.local_participant.calls) == 1
    call = room.local_participant.calls[0]
    assert call.topic == SESSION_PROGRESS_TOPIC
    assert b'"op":"snapshot"' in call.payload or b'"op": "snapshot"' in call.payload
