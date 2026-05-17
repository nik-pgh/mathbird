"""``search_documents`` passes active_doc_id from userdata as doc_ids."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.agent import tools as tools_mod
from app.agent.whiteboard import BoardCache, BoardState, SessionData
from app.rag import retriever as retriever_mod
from app.rag.retriever import RetrievedChunk


class _RecordingRetriever:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def retrieve(
        self,
        query: str,
        *,
        top_k: int = 4,
        doc_ids: tuple[str, ...] = (),
    ) -> list[RetrievedChunk]:
        self.calls.append({"query": query, "top_k": top_k, "doc_ids": doc_ids})
        return [RetrievedChunk(text="hit", source="x.pdf#page=1")]

    async def ingest_pdf(self, path: str, *, doc_id: str) -> None:  # noqa: ARG002
        return None


def _fake_ctx(userdata: Any) -> Any:
    return SimpleNamespace(session=SimpleNamespace(userdata=userdata))


def _search_callable():
    """Return the underlying async function from the @function_tool wrapper.

    livekit-agents wraps decorated tools; the bare callable is reachable via
    a few possible attributes depending on the SDK version. Probe in order.
    """
    tool = tools_mod.search_documents
    for attr in ("fnc", "fn", "callable", "__wrapped__"):
        fn = getattr(tool, attr, None)
        if fn is not None and callable(fn):
            return fn
    if callable(tool):
        return tool
    raise AssertionError(
        f"could not locate the underlying callable on search_documents (attrs: {dir(tool)})"
    )


async def test_search_documents_passes_active_doc_id(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _RecordingRetriever()
    monkeypatch.setattr(retriever_mod, "_singleton", recorder)

    session_data = SessionData(
        board_state=BoardState(),
        board_cache=BoardCache(),
        active_doc_id="textbook-42",
    )

    result = await _search_callable()(_fake_ctx(session_data), query="page 7")
    assert "hit" in result
    assert recorder.calls == [{"query": "page 7", "top_k": 4, "doc_ids": ("textbook-42",)}]


async def test_search_documents_no_active_doc_id_passes_empty_tuple(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = _RecordingRetriever()
    monkeypatch.setattr(retriever_mod, "_singleton", recorder)

    session_data = SessionData(
        board_state=BoardState(),
        board_cache=BoardCache(),
        active_doc_id=None,
    )

    await _search_callable()(_fake_ctx(session_data), query="page 7")
    assert recorder.calls[0]["doc_ids"] == ()
