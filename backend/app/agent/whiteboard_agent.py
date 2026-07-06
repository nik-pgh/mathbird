"""``Agent`` subclass that drives the AiBoard from the agent's spoken reply.

Responsibilities:

1. Delegate per-turn context injection via ``on_user_turn_completed`` →
   :func:`app.agent.turn_context.prepare.prepare_turn_context` (board reading,
   progress blocks, grading, textbook excerpts when RAG is enabled).
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

from app.agent.grader.base import Grader
from app.agent.math_speech import spoken_math_stream
from app.agent.turn_context.grading_task import PendingGrader
from app.agent.turn_context.prepare import prepare_turn_context
from app.agent.turn_context.session import resolve_agent_session, resolve_session_data
from app.agent.whiteboard.cache import BoardCache
from app.agent.whiteboard.extractor.base import BoardExtractor
from app.agent.whiteboard.messages import AiBoardUpdate
from app.agent.whiteboard.publisher import publish_ai_board
from app.agent.whiteboard.sentence import split_sentences
from app.agent.whiteboard.state import BoardState
from app.config import get_settings
from app.progress.engine import ProgressEngine
from app.rag import get_retriever

logger = logging.getLogger("mathbird.agent.extractor")


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
        queue_size = get_settings().board_extractor_queue_size
        self._sentence_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=queue_size)
        self._queue_maxsize = queue_size
        self._last_prefetched_node_id: str | None = None
        self._last_prefetched_label: str | None = None
        self._last_prefetched_body: str | None = None
        self._buffer: str = ""
        self._last_sentence: str | None = None
        self._worker: asyncio.Task | None = None
        self._pending_grader = PendingGrader()
        # Production: ``self.session`` is set by the framework on bind.
        # Tests inject ``self._fake_session_for_tests`` for the room lookup.
        self._fake_session_for_tests: Any | None = None

    # ── user-board reading injection (unchanged from prior implementation) ──

    async def on_user_turn_completed(
        self,
        turn_ctx: ChatContext,
        new_message: ChatMessage,
    ) -> None:
        await prepare_turn_context(self, turn_ctx, new_message)

    async def _maybe_inject_textbook_excerpt(self, turn_ctx: ChatContext) -> None:
        """Pre-fetch RAG snippets for the current syllabus node when retrieval is enabled."""
        engine = self._progress_engine
        if engine is None:
            return

        settings = get_settings()
        if settings.rag_provider == "null" or settings.rag_prefetch_mode == "null":
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

        node_id = pointer.problem_id or pointer.concept_id
        label = engine.node_label(pointer)

        reuse_cached = (
            settings.rag_prefetch_mode == "focus_change"
            and node_id == self._last_prefetched_node_id
            and self._last_prefetched_body is not None
        )
        if reuse_cached:
            self._inject_textbook_excerpt_message(
                turn_ctx,
                label=self._last_prefetched_label or label,
                body=self._last_prefetched_body,
            )
            return

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

        self._last_prefetched_node_id = node_id
        self._last_prefetched_label = label
        self._last_prefetched_body = "\n\n".join(
            f"[{chunk.source}]\n{chunk.text}" for chunk in chunks
        )
        self._inject_textbook_excerpt_message(
            turn_ctx, label=label, body=self._last_prefetched_body
        )

    def _inject_textbook_excerpt_message(
        self, turn_ctx: ChatContext, *, label: str, body: str
    ) -> None:
        turn_ctx.add_message(
            role="system",
            content=(
                "[textbook excerpt]\n"
                "Coarse preview from the current syllabus focus — NOT a substitute "
                "for lookup. Call search_documents with a specific query (section, "
                "definition, example, page) before explaining or teaching PDF content.\n\n"
                f"Focus preview for {label}:\n\n"
                f"{body}"
            ),
        )

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
        await self._pending_grader.drain()

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
                "extractor queue full (maxsize=%d, qsize=%d); dropping sentence: %r",
                self._queue_maxsize,
                self._sentence_queue.qsize(),
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
