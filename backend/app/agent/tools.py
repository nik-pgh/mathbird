"""Function tools exposed to the LLM during a voice session.

Tools are how the agent calls into our code mid-conversation. Two families today:

* ``search_documents`` — delegates to ``app.rag.get_retriever()`` so voice
  answers can be grounded in uploaded textbook chunks when RAG is enabled.
* ``update_ai_board`` / ``clear_ai_board`` / ``read_user_board`` — the
  whiteboard surface. The agent uses these to write typeset math + plots /
  shapes onto its board and to re-read the student's board mid tool-chain.

Per-room whiteboard state is reached through the framework: ``BoardState``
rides on ``ctx.session.userdata`` (set by the entrypoint when constructing
``AgentSession``), and the LiveKit ``Room`` is available at
``ctx.session.room_io.room``.
"""

from __future__ import annotations

import logging

from livekit.agents import RunContext, function_tool

from app.agent.whiteboard import (
    AiBoardItem,
    AiBoardUpdate,
    BoardState,
    SessionData,
    publish_ai_board,
)
from app.config import get_settings
from app.rag import get_retriever

logger = logging.getLogger("mathbird.agent.tools")


# ── RAG tool (unchanged) ────────────────────────────────────────────────────


@function_tool
async def search_documents(ctx: RunContext, query: str) -> str:
    """Search the student's uploaded PDF (assignment / textbook) and return excerpts.

    Call this BEFORE answering ANY question that could plausibly be about
    the uploaded PDF — a problem, exercise, example, page, section,
    instruction, suggestion, formatting rule, or any concrete content the
    student might be referring to. When in doubt, call it. Do not say "I
    don't know" without calling this first.

    Writing a good ``query``:
    - Use digits, not words: ``"problem 3"`` not ``"problem three"``,
      ``"page 7"`` not ``"page seven"``. The index has fast exact-match
      lookups keyed on numeric problem / page / example IDs; words bypass
      them and fall back to weaker semantic search.
    - Use the PDF's own vocabulary (``problem``, ``exercise``, ``example``,
      ``page``) instead of conversational paraphrases like "the second
      one" or "question number three".
    - For open-ended topics, pass the student's question close to verbatim
      so semantic similarity has full context (e.g.
      ``"how to make solutions legible"`` rather than just
      ``"legibility"``).

    Returns concatenated snippets with source citations. Treat the
    returned snippets as authoritative ground truth; if any come back,
    synthesise the answer from them rather than from prior knowledge.
    """
    settings = get_settings()
    retriever = get_retriever()
    chunks = await retriever.retrieve(query, top_k=settings.rag_top_k)

    if not chunks:
        return "No documents are indexed yet. Tell the user no PDFs have been uploaded."

    return "\n\n".join(f"[{c.source}]\n{c.text}" for c in chunks)


# ── Whiteboard tools ────────────────────────────────────────────────────────


def _board_state(ctx: RunContext) -> BoardState | None:
    """Read the per-session ``BoardState`` set by ``app.agent.main.entrypoint``."""
    try:
        data = ctx.session.userdata
    except Exception:
        return None
    # New shape: SessionData bundles BoardState + BoardCache. Stay tolerant
    # of the legacy bare-BoardState shape so we don't break older sessions
    # mid-rollout (defensive — the new entrypoint always supplies SessionData).
    if isinstance(data, SessionData):
        return data.board_state
    if isinstance(data, BoardState):
        return data
    return None


@function_tool
async def update_ai_board(ctx: RunContext, items: list[AiBoardItem]) -> str:
    """Write or update items on YOUR whiteboard (visible to the student).

    Use this while you explain to: write typeset math, draw a function plot,
    or sketch a shape. Each item's ``id`` controls upsert — pass the same
    ``id`` to replace an item, pass a new ``id`` to append. Keep items small
    and self-contained: one equation or one figure per item.

    Every item MUST include a ``kind`` field naming its type:
    - ``kind="text"`` with ``id`` and ``markdown`` (may contain $...$ LaTeX)
    - ``kind="plot"`` with ``id``, ``expression`` (Python-style in x), and
      optional ``x_min`` / ``x_max`` / ``label``
    - ``kind="shape"`` with ``id`` and ``svg`` (fragment without <svg> wrapper)

    Example call::

        update_ai_board(items=[
            {"kind": "text", "id": "eq1", "markdown": "$2x + 10 = 20$"},
            {"kind": "plot", "id": "p1", "expression": "x**2 - 4"},
        ])
    """
    try:
        update = AiBoardUpdate(op="upsert", items=items)
        room = ctx.session.room_io.room
        await publish_ai_board(room, update)
    except Exception as exc:
        logger.exception("update_ai_board failed: items=%r", items)
        # Return the error to the LLM so it can correct (e.g. add missing
        # ``kind``) rather than apologise to the student. The function-tool
        # layer otherwise replaces uncaught exceptions with a generic "An
        # internal error occurred" that gives the LLM no signal to retry.
        return f"update_ai_board failed: {type(exc).__name__}: {exc}"
    return f"Updated AI whiteboard with {len(items)} item(s)."


@function_tool
async def clear_ai_board(ctx: RunContext) -> str:
    """Wipe YOUR whiteboard. Use when starting a new topic so the board does
    not accumulate stale content. Does not touch the student's board."""
    room = ctx.session.room_io.room
    await publish_ai_board(room, AiBoardUpdate(op="clear"))
    return "AI whiteboard cleared."


@function_tool
async def read_user_board(ctx: RunContext) -> str:
    """Return the most recent reading of the STUDENT's whiteboard.

    The reading is already injected into your context at the start of every
    turn. Call this only when you want to re-read mid-tool-chain (e.g. after
    nudging the student to write something).
    """
    state = _board_state(ctx)
    if state is None:
        return "(student whiteboard: no reading yet)"
    if state.refreshed_at is None:
        return "(student whiteboard: no reading yet)"
    if state.is_blank:
        return "(student whiteboard: blank)"
    return state.user_text


def build_function_tools() -> list:
    """Return the tool set the agent should expose to the LLM.

    AiBoard writes (``update_ai_board`` / ``clear_ai_board``) are NOT in this
    list — the AiBoard is now driven by the per-sentence extractor in
    ``WhiteboardAgent`` rather than direct LLM tool calls. The two functions
    stay defined in this module so the publish primitive is reachable for
    tests and so re-enabling LLM-direct board writes is a one-line change.
    """
    return [search_documents, read_user_board]
