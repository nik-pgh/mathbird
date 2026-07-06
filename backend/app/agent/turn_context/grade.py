"""Post-turn grading: assess student input and advance progress."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from livekit.agents.llm import ChatMessage

from app.agent.grader.base import GradeResult
from app.agent.turn_context.session import resolve_agent_session
from app.progress.engine import ProgressEngine

if TYPE_CHECKING:
    from app.agent.whiteboard_agent import WhiteboardAgent

logger = logging.getLogger("mathbird.agent.grader")


def _extract_text(message: ChatMessage) -> str:
    """Best-effort extraction of plain text from a ChatMessage."""
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


def _last_assistant_message(agent: WhiteboardAgent) -> str | None:
    """Return the most recent non-empty assistant message from session history."""
    sess = resolve_agent_session(agent)
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


async def run_grade_turn_safe(agent: WhiteboardAgent, new_message: ChatMessage) -> None:
    try:
        await grade_student_turn(agent, new_message)
    except Exception:
        logger.exception("background grader task failed")


async def grade_student_turn(agent: WhiteboardAgent, new_message: ChatMessage) -> None:
    """Assess the student's latest turn and advance the student model.

    Defensive: any grader/persistence failure is logged and swallowed so
    the turn proceeds. The ``new_message`` is the student's input text;
    the whiteboard state supplies ``board_text``.
    """
    engine = agent._progress_engine
    if engine is None or agent._grader is None:
        return

    turn_text = _extract_text(new_message)
    if not turn_text.strip():
        return

    focus_node_id = engine.state.focus.problem_id or engine.state.focus.concept_id \
        if engine.state.focus is not None else None
    rec = engine.recommend()
    nxt = engine.compute_next_suggestion()
    grader_target_id = rec.focus_node_id or (
        (nxt.problem_id or nxt.concept_id) if nxt else None
    )
    grader_target_label = (
        engine.label_for_node_id(grader_target_id) if grader_target_id else None
    )
    context_id = focus_node_id or grader_target_id
    levels = engine.nearby_levels(focus_node_id) if focus_node_id else {}
    if context_id is None:
        syllabus_context = ""
    else:
        syllabus_context = engine.focus_context(context_id)
        if (
            grader_target_id
            and grader_target_id != context_id
            and rec.intent in {"advance", "introduce"}
        ):
            syllabus_context = (
                f"{syllabus_context}\n\n--- transition target ---\n"
                f"{engine.focus_context(grader_target_id)}"
            )
    last_tutor_message = _last_assistant_message(agent)
    board_text = None if agent._board_state.is_blank else agent._board_state.user_text

    try:
        result = await agent._grader.grade(
            turn_text=turn_text,
            board_text=board_text,
            focus_node_id=focus_node_id,
            levels=levels,
            syllabus_context=syllabus_context,
            next_suggestion_node_id=grader_target_id,
            next_suggestion_label=grader_target_label,
            recommend_intent=rec.intent,
            recommend_directive=rec.directive,
            last_tutor_message=last_tutor_message,
        )
    except Exception:
        logger.exception("grader raised; skipping turn grading")
        return

    if not result.set_focus_node_id:
        if focus_node_id is None:
            anchor = engine.focus_on_introduce_engagement(turn_text)
        else:
            anchor = engine.focus_on_advance_engagement(turn_text)
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

    try:
        await _persist_progress_via_store(engine)
    except Exception:
        logger.exception("failed to persist graded progress state")
    try:
        room = agent._get_room()
        if room is not None:
            from app.progress.publisher import publish_session_progress

            await publish_session_progress(room, engine.publishable_update())
    except Exception:
        logger.exception("failed to publish graded progress snapshot")
