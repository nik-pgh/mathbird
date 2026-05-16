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


async def test_search_documents_uses_settings_top_k_when_tool_arg_is_not_positive(
    monkeypatch,
) -> None:
    retriever = FakeRetriever()
    monkeypatch.setattr(tools, "get_retriever", lambda: retriever)
    monkeypatch.setattr(tools, "get_settings", lambda: SimpleNamespace(rag_top_k=7))

    result = await tools.search_documents.__wrapped__(None, "explain example 3", top_k=0)

    assert retriever.calls == [("explain example 3", 7)]
    assert "[book.pdf, page 20]\nA useful chunk." in result
