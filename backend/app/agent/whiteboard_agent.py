"""``Agent`` subclass that drives the AiBoard from the agent's spoken reply.

Three responsibilities:

1. Inject the latest reading of the *student's* board into every per-turn
   ChatContext via ``on_user_turn_completed``.
2. Override ``transcription_node`` to tee the agent's outgoing text stream:
   text segments pass through to transcript/AiBoard unchanged, while a side channel
   accumulates segments into sentences and feeds a single background
   extractor worker. The worker calls the configured :class:`BoardExtractor`
   per sentence and publishes the resulting :class:`AiBoardUpdate` over the
   data channel.
3. Override ``tts_node`` to verbalize math notation for speech only.

The TTS path is never blocked by the extractor. State (the per-room
:class:`BoardCache`) is shared between the worker and the next extractor
call so sentence N+1 sees the items emitted by sentence N.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterable
from typing import Any

from livekit.agents import Agent
from livekit.agents.llm import ChatContext, ChatMessage
from opentelemetry import trace

from app.agent.grader.base import Grader, NodeUpdate
from app.agent.math_speech import spoken_math_stream
from app.agent.whiteboard.cache import BoardCache
from app.agent.whiteboard.extractor.base import BoardExtractor
from app.agent.whiteboard.messages import AiBoardUpdate
from app.agent.whiteboard.publisher import publish_ai_board
from app.agent.whiteboard.sentence import split_sentences
from app.agent.whiteboard.state import BoardState
from app.progress.engine import ProgressEngine

logger = logging.getLogger("mathbird.agent.extractor")
_tracer = trace.get_tracer("mathbird.session")

_QUEUE_MAXSIZE = 20


def _extract_text(message: ChatMessage) -> str:
    """Best-effort extraction of plain text from a ChatMessage.

    LiveKit ChatMessage content may be a string or a list of content parts;
    we concatenate any str-like parts.
    """
    content = getattr(message, "content", None)
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    parts: list[str] = []
    if isinstance(content, list):
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            else:
                text = getattr(part, "text", None) or getattr(part, "content", None)
                if isinstance(text, str):
                    parts.append(text)
    return "".join(parts)


async def _persist_progress_via_store(engine: ProgressEngine) -> None:
    from app.progress import get_progress_store
    from app.storage import get_storage

    store = get_progress_store(get_storage())
    await store.save(engine.state)


class WhiteboardAgent(Agent):
    def __init__(
        self,
        *,
        board_state: BoardState,
        board_cache: BoardCache,
        extractor: BoardExtractor,
        grader: Grader | None = None,
        progress_engine: ProgressEngine | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._board_state = board_state
        self._board_cache = board_cache
        self._extractor = extractor
        self._grader = grader
        self._progress_engine = progress_engine
        self._sentence_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
        self._buffer: str = ""
        self._last_sentence: str | None = None
        self._worker: asyncio.Task | None = None
        # Production: ``self.session`` is set by the framework on bind.
        # Tests inject ``self._fake_session_for_tests`` for the room lookup.
        self._fake_session_for_tests: Any | None = None

    # ── user-board reading injection (unchanged from prior implementation) ──

    async def on_user_turn_completed(
        self,
        turn_ctx: ChatContext,
        new_message: ChatMessage,  # noqa: ARG002 — required by framework hook
    ) -> None:
        state = self._board_state

        # Trace the session dynamics that shape this turn's LLM call.
        # Uses NoOp tracer when Phoenix is disabled — zero cost when off.
        with _tracer.start_as_current_span("session.turn_context") as span:
            if state.refreshed_at is not None:
                age = state.age_seconds()
                age_str = f"{age:.0f}s ago" if age is not None else "just now"

                span.set_attribute("session.turn.whiteboard_present", True)
                span.set_attribute("session.turn.whiteboard_age_seconds", age or -1)
                span.set_attribute("session.turn.whiteboard_blank", state.is_blank)
                if not state.is_blank:
                    span.set_attribute("session.turn.whiteboard_text", state.user_text[:500])

                if state.is_blank:
                    body = f"[user whiteboard (refreshed {age_str}): blank]"
                else:
                    body = f"[user whiteboard (refreshed {age_str}):\n{state.user_text}\n]"

                turn_ctx.add_message(role="system", content=body)
            else:
                span.set_attribute("session.turn.whiteboard_present", False)

            if self._progress_engine is not None:
                injection = self._progress_engine.format_injection()
                turn_ctx.add_message(role="system", content=injection)

                engine = self._progress_engine
                summary = engine.summary()
                focus = engine.state.focus
                span.set_attribute("session.turn.progress_mastered", summary.mastered)
                span.set_attribute("session.turn.progress_total", summary.total)
                span.set_attribute("session.turn.progress_in_progress", summary.in_progress)
                if focus:
                    span.set_attribute("session.turn.focus_problem_id", focus.problem_id)
                    span.set_attribute("session.turn.focus_chapter_id", focus.chapter_id)

        # Grade the student's turn and evolve the student model. Runs after the
        # span so a grader failure never breaks the turn; the snapshot publish
        # lets the frontend see updated levels even when the LLM calls no tool.
        if self._progress_engine is not None and self._grader is not None:
            await self._grade_turn(new_message)

    async def _grade_turn(self, new_message: ChatMessage) -> None:
        """Assess the student's latest turn and advance the student model.

        Defensive: any grader/persistence failure is logged and swallowed so
        the turn proceeds. The ``new_message`` is the student's input text;
        the whiteboard state supplies ``board_text``.
        """
        engine = self._progress_engine
        if engine is None or self._grader is None:
            return

        turn_text = _extract_text(new_message)
        if not turn_text.strip():
            return

        focus_node_id = engine.state.focus.problem_id or engine.state.focus.concept_id \
            if engine.state.focus is not None else None
        levels = engine.nearby_levels(focus_node_id) if focus_node_id else {}
        syllabus_context = engine.focus_context(focus_node_id) if focus_node_id else ""
        board_text = None if self._board_state.is_blank else self._board_state.user_text

        try:
            result = await self._grader.grade(
                turn_text=turn_text,
                board_text=board_text,
                focus_node_id=focus_node_id,
                levels=levels,
                syllabus_context=syllabus_context,
            )
        except Exception:
            logger.exception("grader raised; skipping turn grading")
            return

        if not result.updates:
            return

        changed = False
        for update in result.updates:
            try:
                changed |= self._apply_grader_update(engine, update)
            except ValueError:
                logger.warning("grader referenced unknown node id: %s", update.node_id)

        if not changed:
            return

        # Persist + publish so the frontend reflects grader-driven evolution
        # even when the LLM called no progress tool this turn.
        try:
            await _persist_progress_via_store(engine)
        except Exception:
            logger.exception("failed to persist graded progress state")
        try:
            room = self._get_room()
            if room is not None:
                from app.progress.publisher import publish_session_progress

                await publish_session_progress(room, engine.snapshot_update())
        except Exception:
            logger.exception("failed to publish graded progress snapshot")

    @staticmethod
    def _apply_grader_update(engine: ProgressEngine, update: NodeUpdate) -> bool:
        """Apply one graded update; return True if it changed state."""
        before = engine.effective_level(update.node_id)
        if update.clear_misconceptions:
            engine.clear_misconceptions(update.node_id)
        for text in update.misconception_additions:
            engine.record_misconception(update.node_id, text)
        if update.hint_given:
            engine.record_hint(update.node_id)
        if update.level is not None:
            engine.set_level(
                update.node_id,
                update.level,
                note=update.note or None,
                force=update.force,
            )
        elif update.note:
            # Note-only update: touch the node so its updated_at moves.
            engine.set_level(update.node_id, engine.effective_level(update.node_id), note=update.note)
        after = engine.effective_level(update.node_id)
        return after != before or bool(update.misconception_additions) or update.clear_misconceptions \
            or update.hint_given

    # ── lifecycle ──────────────────────────────────────────────────────

    async def on_enter(self) -> None:
        self._worker = asyncio.create_task(self._extractor_worker_loop())

    async def on_exit(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            try:
                await asyncio.wait_for(self._worker, timeout=1.0)
            except (TimeoutError, asyncio.CancelledError):
                pass
            self._worker = None

    # ── transcription_node tap ─────────────────────────────────────────

    async def transcription_node(  # type: ignore[override]
        self,
        text: AsyncIterable[Any],
        model_settings: Any,  # noqa: ARG002 — framework hook
    ) -> AsyncIterable[Any]:
        async for segment in text:
            self._buffer += str(segment)
            sentences, remainder = split_sentences(self._buffer)
            self._buffer = remainder
            for sentence in sentences:
                self._enqueue_sentence(sentence)
            yield segment

        # End of stream — flush any non-empty trailing partial as a final sentence.
        tail = self._buffer.strip()
        self._buffer = ""
        if tail:
            self._enqueue_sentence(tail)

    def tts_node(  # type: ignore[override]
        self,
        text: AsyncIterable[str],
        model_settings: Any,
    ) -> Any:
        return super().tts_node(spoken_math_stream(text), model_settings)

    def _enqueue_sentence(self, sentence: str) -> None:
        try:
            self._sentence_queue.put_nowait(sentence)
        except asyncio.QueueFull:
            logger.warning(
                "extractor queue full (maxsize=%d); dropping sentence: %r",
                _QUEUE_MAXSIZE,
                sentence[:80],
            )

    # ── worker ─────────────────────────────────────────────────────────

    async def _extractor_worker_loop(self) -> None:
        while True:
            try:
                sentence = await self._sentence_queue.get()
                await self._process_sentence(sentence)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("extractor worker error; continuing")

    async def _process_sentence(self, sentence: str) -> None:
        current = self._board_cache.current_items()
        items = await self._extractor.extract(
            sentence=sentence,
            current_items=current,
            last_sentence=self._last_sentence,
        )
        self._last_sentence = sentence
        if not items:
            return
        room = self._get_room()
        if room is None:
            logger.warning("no room available; dropping %d board item(s)", len(items))
            return
        await publish_ai_board(room, AiBoardUpdate(op="upsert", items=items))
        self._board_cache.apply(items)

    def _get_room(self) -> Any | None:
        # Tests set ``self._fake_session_for_tests``. Production reads
        # ``self.session`` set by the framework on bind.
        sess = self._fake_session_for_tests
        if sess is None:
            sess = getattr(self, "session", None)
        if sess is None:
            return None
        try:
            return sess.room_io.room
        except Exception:
            return None
