"""Shared per-turn context preparation for voice and text sessions."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from livekit.agents.llm import ChatContext, ChatMessage
from opentelemetry import trace

from app.agent.turn_context.builder import TurnContextBuilder
from app.agent.turn_context.grade import run_grade_turn_safe
from app.agent.turn_context.snapshot import snapshot_from_turn_ctx
from app.agent.turn_context.types import TurnContextSnapshot

if TYPE_CHECKING:
    from app.agent.whiteboard_agent import WhiteboardAgent

_tracer = trace.get_tracer("mathbird.session")


@dataclass(frozen=True)
class PreparedTurnContext:
    snapshot: TurnContextSnapshot
    grading_task: asyncio.Task[None] | None


async def prepare_turn_context(
    agent: WhiteboardAgent,
    turn_ctx: ChatContext,
    new_message: ChatMessage,
) -> PreparedTurnContext:
    """Inject per-turn system context, schedule grading, return a snapshot."""
    await agent._pending_grader.drain()

    state = agent._board_state

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
            board_cache=agent._board_cache,
            progress_engine=agent._progress_engine,
        )
        for block in builder.base_injections():
            turn_ctx.add_message(role="system", content=block.content)

        if agent._progress_engine is not None:
            await agent._maybe_inject_textbook_excerpt(turn_ctx)

            engine = agent._progress_engine
            summary = engine.summary()
            focus = engine.state.focus
            span.set_attribute("session.turn.progress_mastered", summary.mastered)
            span.set_attribute("session.turn.progress_total", summary.total)
            span.set_attribute("session.turn.progress_in_progress", summary.in_progress)
            if focus:
                span.set_attribute("session.turn.focus_problem_id", focus.problem_id)
                span.set_attribute("session.turn.focus_chapter_id", focus.chapter_id)

    snapshot = snapshot_from_turn_ctx(turn_ctx)

    grading_task: asyncio.Task[None] | None = None
    if agent._progress_engine is not None and agent._grader is not None:
        grading_task = agent._pending_grader.schedule(
            run_grade_turn_safe(agent, new_message),
        )

    return PreparedTurnContext(snapshot, grading_task)
