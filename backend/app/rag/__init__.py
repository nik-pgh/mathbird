"""RAG layer.

The agent talks to a :class:`Retriever` — a thin interface that returns
relevant document snippets for a query. The current implementation is a no-op
stub so the rest of the system runs without a vector store wired up.

When you pick a RAG framework (LlamaIndex, LangChain, OpenAI File Search, ...),
add a new ``Retriever`` implementation in this package and swap it in
``get_retriever()``. Nothing else needs to change.
"""

from .retriever import NullRetriever, RetrievedChunk, Retriever, get_retriever

__all__ = ["NullRetriever", "Retriever", "RetrievedChunk", "get_retriever"]
