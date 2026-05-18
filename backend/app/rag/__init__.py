"""RAG layer.

The agent talks to a :class:`Retriever` — a thin interface that returns
relevant document snippets for a query. The default ``RAG_PROVIDER=null``
returns :class:`NullRetriever` so the rest of the system runs without a vector
store. ``RAG_PROVIDER=llamaindex_qdrant`` enables the built-in LlamaParse,
LlamaIndex, and Qdrant implementation.

Additional providers should live in this package and be selected by
``get_retriever()`` so callers do not change when the backend changes.
"""

from .retriever import NullRetriever, RetrievedChunk, Retriever, get_retriever

__all__ = ["NullRetriever", "Retriever", "RetrievedChunk", "get_retriever"]
