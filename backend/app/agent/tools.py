"""Function tools exposed to the LLM during a voice session.

Tools are how the agent calls into our code mid-conversation. The retrieval
tool delegates to ``app.rag.get_retriever()`` so voice answers can be grounded
in uploaded textbook chunks when RAG is enabled.
"""

from __future__ import annotations

import logging

from livekit.agents import RunContext, function_tool

from app.config import get_settings
from app.rag import get_retriever

logger = logging.getLogger("mathbird.agent.tools")


@function_tool
async def search_documents(
    ctx: RunContext,
    query: str,
    top_k: int = 0,
    doc_id: str = "",
) -> str:
    """Search the user's uploaded PDF documents for information relevant to ``query``.

    Use this whenever the user asks about content from their documents.
    Returns concatenated snippets with source citations, or a brief note if no
    documents are indexed yet.
    """
    effective_top_k = top_k if top_k > 0 else get_settings().rag_top_k
    retriever = get_retriever()
    doc_ids = (doc_id,) if doc_id else ()
    chunks = await retriever.retrieve(query, top_k=effective_top_k, doc_ids=doc_ids)

    if not chunks:
        return "No documents are indexed yet. Tell the user no PDFs have been uploaded."

    return "\n\n".join(f"[{c.source}]\n{c.text}" for c in chunks)


def build_function_tools() -> list:
    """Return the tool set the agent should expose to the LLM.

    Add new ``@function_tool`` functions here as capabilities grow.
    """
    return [search_documents]
