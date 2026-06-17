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

from app.agent.math_speech import spoken_math_stream
from app.agent.whiteboard.cache import BoardCache
from app.agent.whiteboard.extractor.base import BoardExtractor
from app.agent.whiteboard.messages import AiBoardUpdate
from app.agent.whiteboard.publisher import publish_ai_board
from app.agent.whiteboard.sentence import split_sentences
from app.agent.whiteboard.state import BoardState

logger = logging.getLogger("mathbird.agent.extractor")

_QUEUE_MAXSIZE = 20


class WhiteboardAgent(Agent):
    def __init__(
        self,
        *,
        board_state: BoardState,
        board_cache: BoardCache,
        extractor: BoardExtractor,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._board_state = board_state
        self._board_cache = board_cache
        self._extractor = extractor
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
        if state.refreshed_at is None:
            return

        age = state.age_seconds()
        age_str = f"{age:.0f}s ago" if age is not None else "just now"

        if state.is_blank:
            body = f"[user whiteboard (refreshed {age_str}): blank]"
        else:
            body = f"[user whiteboard (refreshed {age_str}):\n{state.user_text}\n]"

        turn_ctx.add_message(role="system", content=body)

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
