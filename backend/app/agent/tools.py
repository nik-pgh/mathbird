"""Function tools exposed to the LLM during a voice session.

Tools are how the agent calls into our code mid-conversation. The retrieval
tool is the seam where the future RAG framework plugs in — when
``app.rag.get_retriever()`` returns something non-null, this tool starts
returning real chunks and the LLM will start grounding answers on them.
"""

from __future__ import annotations

import logging

from livekit.agents import RunContext, function_tool

from app.rag import get_retriever

logger = logging.getLogger("mathbird.agent.tools")


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


def build_function_tools() -> list:
    """Return the tool set the agent should expose to the LLM.

    Add new ``@function_tool`` functions here as capabilities grow.
    """
    return [search_documents]
