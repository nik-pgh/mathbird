"""Function tools exposed to the LLM during a voice session.

Tools are how the agent calls into our code mid-conversation. We register two
families today:

* ``search_documents`` — the existing RAG seam (no-op until a real
  ``Retriever`` is wired in).
* ``update_ai_board`` / ``clear_ai_board`` / ``read_user_board`` — the
  whiteboard surface. The agent uses these to write typeset math + plots /
  shapes onto its board and to re-read the student's board mid tool-chain.

Per-room state is reached through the framework: ``BoardState`` rides on
``ctx.session.userdata`` (set by the entrypoint when constructing
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
    publish_ai_board,
)
from app.rag import get_retriever

logger = logging.getLogger("mathbird.agent.tools")


# ── RAG tool (unchanged) ────────────────────────────────────────────────────


@function_tool
async def search_documents(
    ctx: RunContext,
    query: str,
    top_k: int = 4,
) -> str:
    """Search the user's uploaded PDF documents for information relevant to ``query``.

    Use this whenever the user asks about content from their documents.
    Returns concatenated snippets with source citations, or a brief note if no
    documents are indexed yet.
    """
    retriever = get_retriever()
    chunks = await retriever.retrieve(query, top_k=top_k)

    if not chunks:
        return "No documents are indexed yet. Tell the user no PDFs have been uploaded."

    return "\n\n".join(f"[{c.source}]\n{c.text}" for c in chunks)


# ── Whiteboard tools ────────────────────────────────────────────────────────


def _board_state(ctx: RunContext) -> BoardState | None:
    """Read the per-session ``BoardState`` set by ``app.agent.main.entrypoint``."""
    try:
        state = ctx.session.userdata
    except Exception:
        return None
    return state if isinstance(state, BoardState) else None


@function_tool
async def update_ai_board(ctx: RunContext, items: list[AiBoardItem]) -> str:
    """Write or update items on YOUR whiteboard (visible to the student).

    Use this while you explain to: write typeset math (`AiBoardText` with $...$
    LaTeX), draw a function plot (`AiBoardPlot` over `x_min..x_max`), or sketch
    a shape (`AiBoardShape`, sanitized SVG fragment). Each item's `id` controls
    upsert: pass the same `id` to replace an item, pass a new `id` to append.
    Keep items small and self-contained — one equation or one figure per item.
    """
    update = AiBoardUpdate(op="upsert", items=items)
    room = ctx.session.room_io.room
    await publish_ai_board(room, update)
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
    """Return the tool set the agent should expose to the LLM."""
    return [search_documents, update_ai_board, clear_ai_board, read_user_board]
