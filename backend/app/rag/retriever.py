"""Retriever protocol + no-op default.

A ``Retriever`` is whatever can answer "given this query, what document
snippets are relevant?". Today nothing is wired up, so :class:`NullRetriever`
returns an empty list. When you add LlamaIndex/LangChain/etc., implement this
protocol and return the new instance from :func:`get_retriever`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.config import Settings, get_settings


@dataclass(frozen=True)
class RetrievedChunk:
    """A single retrieved snippet."""

    text: str
    source: str  # e.g. "filename.pdf#page=4"
    score: float | None = None


@runtime_checkable
class Retriever(Protocol):
    """Anything that can fetch document snippets for a query."""

    async def retrieve(self, query: str, *, top_k: int = 4) -> list[RetrievedChunk]: ...

    async def ingest_pdf(self, path: str, *, doc_id: str) -> None:
        """Add a PDF to the index. Called when a new PDF is uploaded."""


class NullRetriever:
    """Placeholder retriever. Replace when wiring up a real RAG framework."""

    async def retrieve(self, query: str, *, top_k: int = 4) -> list[RetrievedChunk]:
        return []

    async def ingest_pdf(self, path: str, *, doc_id: str) -> None:
        return None


_singleton: Retriever | None = None


def get_retriever() -> Retriever:
    """Return the process-wide retriever instance."""
    global _singleton
    if _singleton is not None:
        return _singleton

    settings = get_settings()
    if settings.rag_provider == "null":
        _singleton = NullRetriever()
    elif settings.rag_provider == "llamaindex_qdrant":
        _singleton = _build_llamaindex_qdrant_retriever(settings)
    else:
        raise ValueError(f"Unsupported RAG provider: {settings.rag_provider}")

    return _singleton


def _build_llamaindex_qdrant_retriever(settings: Settings) -> Retriever:
    if not settings.llamaparse_api_key:
        raise RuntimeError("LLAMAPARSE_API_KEY is required when RAG_PROVIDER=llamaindex_qdrant.")
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required when RAG_PROVIDER=llamaindex_qdrant.")

    from llama_index.core import StorageContext, VectorStoreIndex
    from llama_index.embeddings.openai import OpenAIEmbedding
    from llama_index.vector_stores.qdrant import QdrantVectorStore
    from qdrant_client import AsyncQdrantClient

    from app.rag.llamaindex_qdrant import LlamaIndexQdrantRetriever, QdrantTextbookStore
    from app.rag.llamaparse_parser import LlamaParseParser

    qdrant_client = AsyncQdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
    )
    vector_store = QdrantVectorStore(
        aclient=qdrant_client,
        collection_name=settings.qdrant_collection,
    )
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    embed_model = OpenAIEmbedding(
        model=settings.embedding_model,
        api_key=settings.openai_api_key,
    )
    index = VectorStoreIndex.from_vector_store(
        vector_store=vector_store,
        storage_context=storage_context,
        embed_model=embed_model,
    )
    parser = LlamaParseParser(
        api_key=settings.llamaparse_api_key,
        tier=settings.llamaparse_tier,
        version=settings.llamaparse_version,
    )
    store = QdrantTextbookStore(
        qdrant_client=qdrant_client,
        collection_name=settings.qdrant_collection,
        index=index,
    )
    return LlamaIndexQdrantRetriever(parser=parser, index=index, store=store)
