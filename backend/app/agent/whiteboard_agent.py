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

from app.agent.grader.base import Grader, GradeResult
from app.agent.math_speech import spoken_math_stream
from app.agent.turn_context.builder import TurnContextBuilder
from app.agent.turn_context.session import resolve_agent_session, resolve_session_data
from app.agent.whiteboard.cache import BoardCache
from app.agent.whiteboard.extractor.base import BoardExtractor
from app.agent.whiteboard.messages import AiBoardUpdate
from app.agent.whiteboard.publisher import publish_ai_board
from app.agent.whiteboard.sentence import split_sentences
from app.agent.whiteboard.state import BoardState
from app.config import get_settings
from app.progress.engine import ProgressEngine, _node_label
from app.rag import get_retriever

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

                span.set_attribute("session.turn.whiteboard_present", True)
                span.set_attribute("session.turn.whiteboard_age_seconds", age or -1)
                span.set_attribute("session.turn.whiteboard_blank", state.is_blank)
                if not state.is_blank:
                    span.set_attribute("session.turn.whiteboard_text", state.user_text[:500])
            else:
                span.set_attribute("session.turn.whiteboard_present", False)

            builder = TurnContextBuilder(
                board_state=state,
                progress_engine=self._progress_engine,
            )
            for block in builder.base_injections():
                turn_ctx.add_message(role="system", content=block.content)

            if self._progress_engine is not None:
                await self._maybe_inject_textbook_excerpt(turn_ctx)

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

    async def _maybe_inject_textbook_excerpt(self, turn_ctx: ChatContext) -> None:
        """Pre-fetch RAG snippets for the current syllabus node when retrieval is enabled."""
        engine = self._progress_engine
        if engine is None:
            return

        settings = get_settings()
        if settings.rag_provider == "null":
            return

        session_data = resolve_session_data(self)
        active_doc_id = session_data.active_doc_id if session_data else None
        if not active_doc_id:
            return

        rec = engine.recommend()
        if rec.focus_node_id is None:
            return

        pointer = engine.state.focus or engine.state.next_suggestion
        if pointer is None:
            return
        label = _node_label(engine.syllabus, pointer)

        try:
            chunks = await get_retriever().retrieve(
                label,
                top_k=settings.rag_top_k,
                doc_ids=(active_doc_id,),
            )
        except Exception:
            logger.exception("textbook excerpt retrieval failed")
            return

        if not chunks:
            return

        body = "\n\n".join(f"[{chunk.source}]\n{chunk.text}" for chunk in chunks)
        turn_ctx.add_message(
            role="system",
            content=(
                "[textbook excerpt]\n"
                f"Use this material from the uploaded PDF when teaching {label}:\n\n"
                f"{body}"
            ),
        )

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
        rec = engine.recommend()
        nxt = engine.state.next_suggestion
        nxt_id = (nxt.problem_id or nxt.concept_id) if nxt else None
        nxt_label = _node_label(engine.syllabus, nxt) if nxt else None
        context_id = focus_node_id or nxt_id
        levels = engine.nearby_levels(focus_node_id) if focus_node_id else {}
        if context_id is None:
            syllabus_context = ""
        elif focus_node_id:
            syllabus_context = engine.focus_context(context_id)
        else:
            syllabus_context = engine.suggestion_context(context_id)
        last_tutor_message = self._last_assistant_message()
        board_text = None if self._board_state.is_blank else self._board_state.user_text

        try:
            result = await self._grader.grade(
                turn_text=turn_text,
                board_text=board_text,
                focus_node_id=focus_node_id,
                levels=levels,
                syllabus_context=syllabus_context,
                next_suggestion_node_id=nxt_id,
                next_suggestion_label=nxt_label,
                recommend_intent=rec.intent,
                recommend_directive=rec.directive,
                last_tutor_message=last_tutor_message,
            )
        except Exception:
            logger.exception("grader raised; skipping turn grading")
            return

        if not result.set_focus_node_id and focus_node_id is None:
            anchor = engine.focus_on_introduce_engagement(turn_text)
            if anchor:
                result = GradeResult(
                    set_focus_node_id=anchor,
                    updates=list(result.updates),
                )

        if not result.updates and not result.set_focus_node_id:
            return

        changed = engine.apply_grade_result(result)

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

    def _last_assistant_message(self) -> str | None:
        """Return the most recent non-empty assistant message from session history."""
        sess = resolve_agent_session(self)
        history = getattr(sess, "history", None) if sess is not None else None
        items = getattr(history, "items", None)
        if not isinstance(items, list):
            return None
        for item in reversed(items):
            role = getattr(item, "role", None)
            if role != "assistant":
                continue
            text = getattr(item, "text_content", None)
            if isinstance(text, str) and text.strip():
                return text
            extracted = _extract_text(item)
            if extracted.strip():
                return extracted
        return None

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
        # Check for a room *before* paying for the extractor call. The local
        # text console starts the session without a room (no RoomIO on an
        # unconnected fake room), and there's no point running the extractor
        # LLM when we already know the items can't be published.
        if self._get_room() is None:
            return
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
            logger.debug("room dropped after extract; dropping %d board item(s)", len(items))
            return
        await publish_ai_board(room, AiBoardUpdate(op="upsert", items=items))
        self._board_cache.apply(items)

    def _get_room(self) -> Any | None:
        sess = resolve_agent_session(self)
        if sess is None:
            return None
        try:
            return sess.room_io.room
        except Exception:
            return None
