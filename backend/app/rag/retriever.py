"""Retriever protocol + no-op default.

A ``Retriever`` is whatever can answer "given this query, what document
snippets are relevant?". Today nothing is wired up, so :class:`NullRetriever`
returns an empty list. When you add LlamaIndex/LangChain/etc., implement this
protocol and return the new instance from :func:`get_retriever`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


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
    """Return the process-wide retriever instance.

    Swap the body of this function (or read from settings) when you add a
    concrete framework. Keeping it as a single accessor means agent and API
    code never need to change.
    """
    global _singleton
    if _singleton is None:
        _singleton = NullRetriever()
    return _singleton
