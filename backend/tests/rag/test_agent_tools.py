from __future__ import annotations

from types import SimpleNamespace

from app.agent import tools
from app.rag.retriever import RetrievedChunk


class FakeRetriever:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    async def retrieve(self, query: str, *, top_k: int = 4):
        self.calls.append((query, top_k))
        return [RetrievedChunk(text="A useful chunk.", source="book.pdf, page 20")]


async def test_search_documents_uses_settings_top_k(monkeypatch) -> None:
    retriever = FakeRetriever()
    monkeypatch.setattr(tools, "get_retriever", lambda: retriever)
    monkeypatch.setattr(tools, "get_settings", lambda: SimpleNamespace(rag_top_k=7))

    result = await tools.search_documents(None, "explain example 3")

    assert retriever.calls == [("explain example 3", 7)]
    assert "[book.pdf, page 20]\nA useful chunk." in result


async def test_search_documents_returns_no_documents_notice_when_empty(monkeypatch) -> None:
    class EmptyRetriever:
        async def retrieve(self, query: str, *, top_k: int = 4):
            return []

    monkeypatch.setattr(tools, "get_retriever", EmptyRetriever)
    monkeypatch.setattr(tools, "get_settings", lambda: SimpleNamespace(rag_top_k=4))

    result = await tools.search_documents(None, "whatever")

    assert "No documents are indexed" in result


async def test_search_documents_concatenates_chunks_with_sources(monkeypatch) -> None:
    class TwoChunkRetriever:
        async def retrieve(self, query: str, *, top_k: int = 4):
            return [
                RetrievedChunk(text="First chunk text.", source="a.pdf, page 1"),
                RetrievedChunk(text="Second chunk text.", source="a.pdf, page 2"),
            ]

    monkeypatch.setattr(tools, "get_retriever", TwoChunkRetriever)
    monkeypatch.setattr(tools, "get_settings", lambda: SimpleNamespace(rag_top_k=4))

    result = await tools.search_documents(None, "anything")

    assert "[a.pdf, page 1]\nFirst chunk text." in result
    assert "[a.pdf, page 2]\nSecond chunk text." in result
