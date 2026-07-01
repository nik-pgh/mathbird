"""Build a per-room agent session bundle shared by the worker entrypoint and simulators."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass

from livekit.agents import AgentSession, JobContext

from app.agent.providers import build_llm, build_stt, build_tts, build_vad
from app.agent.tools import build_function_tools
from app.agent.whiteboard import (
    BoardCache,
    BoardState,
    SessionData,
    UserBoardListenerHandle,
    get_board_extractor,
    get_board_reader,
    install_user_board_listener,
)
from app.agent.grader import Grader, get_grader
from app.agent.whiteboard_agent import WhiteboardAgent
from app.config import Settings, get_settings

logger = logging.getLogger("mathbird.agent")


@dataclass
class SessionBundle:
    session: AgentSession
    agent: WhiteboardAgent
    session_data: SessionData
    listener: UserBoardListenerHandle


def parse_participant_metadata(metadata: str | None) -> tuple[str | None, str | None]:
    if not metadata:
        return None, None
    try:
        payload = json.loads(metadata)
    except (TypeError, ValueError):
        return None, None
    if not isinstance(payload, dict):
        return None, None
    user_id = payload.get("user_id")
    active_doc_id = payload.get("active_doc_id")
    return (
        user_id if isinstance(user_id, str) and user_id else None,
        active_doc_id if isinstance(active_doc_id, str) and active_doc_id else None,
    )


async def resolve_session_identity(ctx: JobContext) -> tuple[str | None, str | None]:
    """Resolve ``user_id`` and ``active_doc_id`` from the joining participant's JWT metadata."""
    try:
        participant = await asyncio.wait_for(ctx.wait_for_participant(), timeout=10.0)
        return parse_participant_metadata(participant.metadata)
    except Exception:
        logger.exception("Failed to read participant metadata; proceeding without doc filter.")
        return None, None


async def _load_progress_engine(user_id: str, doc_id: str):
    from datetime import UTC, datetime

    from app.progress import ProgressEngine, ProgressState, get_progress_store
    from app.storage import get_storage
    from app.syllabus import load_syllabus

    storage = get_storage()
    syllabus = await load_syllabus(storage, doc_id)
    if syllabus is None:
        return None, None

    store = get_progress_store(storage)
    state = await store.load(user_id, doc_id)
    if state is None:
        state = ProgressState(
            user_id=user_id,
            doc_id=doc_id,
            updated_at=datetime.now(UTC).isoformat(),
        )
    engine = ProgressEngine(syllabus=syllabus, state=state)
    return syllabus, engine


async def build_session_bundle(
    *,
    room: object,
    settings: Settings | None = None,
    user_id: str | None = None,
    active_doc_id: str | None = None,
    text_only: bool = False,
    grader: Grader | None = None,
) -> SessionBundle:
    """Wire STT/LLM/TTS/VAD, whiteboard state, tools, and ``WhiteboardAgent``.

    When ``text_only`` is true (console / YAML simulators), only the LLM is wired;
    STT/TTS/VAD and turn detection are omitted.
    """
    settings = settings or get_settings()

    board_state = BoardState()
    board_cache = BoardCache()
    board_reader = get_board_reader()
    board_extractor = get_board_extractor()
    grader = grader if grader is not None else get_grader()
    listener = install_user_board_listener(
        room=room,
        state=board_state,
        reader=board_reader,
        interval=settings.board_reader_interval_seconds,
    )

    syllabus = None
    progress_engine = None
    if user_id and active_doc_id:
        try:
            syllabus, progress_engine = await _load_progress_engine(user_id, active_doc_id)
        except Exception:
            logger.exception(
                "Failed to load progress for user_id=%s doc_id=%s",
                user_id,
                active_doc_id,
            )

    if progress_engine is not None and settings.grader == "null":
        logger.warning(
            "Progress tracking loaded but GRADER=null — progress will not advance. "
            "Set GRADER=openai for grader-primary sessions."
        )

    session_data = SessionData(
        board_state=board_state,
        board_cache=board_cache,
        active_doc_id=active_doc_id,
        user_id=user_id,
        syllabus=syllabus,
        progress_engine=progress_engine,
    )

    if text_only:
        session = AgentSession(
            llm=build_llm(settings),
            turn_detection=None,
            userdata=session_data,
        )
    else:
        session = AgentSession(
            stt=build_stt(settings),
            llm=build_llm(settings),
            tts=build_tts(settings),
            vad=build_vad(settings),
            userdata=session_data,
        )

    agent = WhiteboardAgent(
        instructions=settings.agent_instructions,
        tools=build_function_tools(include_progress=progress_engine is not None),
        board_state=board_state,
        board_cache=board_cache,
        extractor=board_extractor,
        grader=grader,
        progress_engine=progress_engine,
    )

    return SessionBundle(
        session=session,
        agent=agent,
        session_data=session_data,
        listener=listener,
    )


async def send_initial_greeting(session: AgentSession, *, has_progress: bool) -> None:
    if has_progress:
        await session.generate_reply(
            instructions=(
                "Greet briefly. If session progress shows a current focus, offer to "
                "continue there or jump to another problem."
            )
        )
    else:
        await session.generate_reply(
            instructions="Greet the user briefly and ask how you can help."
        )
