from __future__ import annotations

from types import SimpleNamespace

from app.agent import tools
from app.rag.retriever import RetrievedChunk


class FakeRetriever:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    async def retrieve(self, query: str, *, top_k: int = 4, doc_ids: tuple[str, ...] = ()):
        self.calls.append((query, top_k, doc_ids))
        return [RetrievedChunk(text="A useful chunk.", source="book.pdf, page 20")]


async def test_search_documents_uses_settings_top_k_when_tool_arg_is_not_positive(
    monkeypatch,
) -> None:
    retriever = FakeRetriever()
    monkeypatch.setattr(tools, "get_retriever", lambda: retriever)
    monkeypatch.setattr(tools, "get_settings", lambda: SimpleNamespace(rag_top_k=7))

    result = await tools.search_documents.__wrapped__(None, "explain example 3", top_k=0)

    assert retriever.calls == [("explain example 3", 7, ())]
    assert "[book.pdf, page 20]\nA useful chunk." in result


async def test_search_documents_uses_settings_top_k_when_tool_arg_is_omitted(
    monkeypatch,
) -> None:
    retriever = FakeRetriever()
    monkeypatch.setattr(tools, "get_retriever", lambda: retriever)
    monkeypatch.setattr(tools, "get_settings", lambda: SimpleNamespace(rag_top_k=6))

    await tools.search_documents.__wrapped__(None, "explain example 4")

    assert retriever.calls == [("explain example 4", 6, ())]


async def test_search_documents_passes_document_scope(monkeypatch) -> None:
    retriever = FakeRetriever()
    monkeypatch.setattr(tools, "get_retriever", lambda: retriever)
    monkeypatch.setattr(tools, "get_settings", lambda: SimpleNamespace(rag_top_k=4))

    await tools.search_documents.__wrapped__(
        None,
        "help me with problem 8 on page 37",
        doc_id="doc-1",
    )

    assert retriever.calls == [("help me with problem 8 on page 37", 4, ("doc-1",))]
