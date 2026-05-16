"""Concrete Retriever backed by LlamaParse, LlamaIndex, and Qdrant."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from app.rag.formatter import format_records_as_chunks
from app.rag.indexing import parsed_document_to_nodes
from app.rag.parsing import BlockType, RetrievalRequest, RetrievedRecord, TextbookParser
from app.rag.query_parser import parse_retrieval_query
from app.rag.retriever import RetrievedChunk

VALID_BLOCK_TYPES: frozenset[str] = frozenset(
    {
        "heading",
        "paragraph",
        "equation",
        "image",
        "graph",
        "table",
        "example",
        "exercise",
        "instruction",
        "unknown",
    }
)


def _block_type_from_metadata(value: Any) -> BlockType:
    block_type = str(value or "unknown")
    if block_type not in VALID_BLOCK_TYPES:
        return "unknown"
    return cast(BlockType, block_type)


class LlamaIndexQdrantRetriever:
    def __init__(
        self,
        *,
        parser: TextbookParser,
        index: Any,
        store: Any,
        filename_resolver: Callable[[str], str] | None = None,
    ) -> None:
        self.parser = parser
        self.index = index
        self.store = store
        self.filename_resolver = filename_resolver or (lambda path: Path(path).name)

    async def ingest_pdf(self, path: str, *, doc_id: str) -> None:
        filename = self.filename_resolver(path)
        document = await self.parser.parse_pdf(path, doc_id=doc_id, filename=filename)
        nodes = parsed_document_to_nodes(document)
        if nodes:
            await self.index.ainsert_nodes(nodes)

    async def retrieve(self, query: str, *, top_k: int = 4) -> list[RetrievedChunk]:
        parsed = parse_retrieval_query(query)
        request = RetrievalRequest(
            query=query,
            top_k=top_k,
            page_number=parsed.page_number,
            exercise_number=parsed.exercise_number,
        )

        if parsed.is_structured_lookup:
            records = await self.store.structured_lookup(request)
            if records:
                return format_records_as_chunks(records)

        records = await self.store.semantic_search(request)
        return format_records_as_chunks(records)


class QdrantTextbookStore:
    def __init__(self, *, qdrant_client: Any, collection_name: str, index: Any) -> None:
        self.qdrant_client = qdrant_client
        self.collection_name = collection_name
        self.index = index

    async def structured_lookup(self, request: RetrievalRequest) -> list[RetrievedRecord]:
        from qdrant_client.http import models

        must: list[Any] = []
        if request.page_number is not None:
            must.append(
                models.FieldCondition(
                    key="metadata.page_number",
                    match=models.MatchValue(value=request.page_number),
                )
            )
        if request.exercise_number:
            must.append(
                models.FieldCondition(
                    key="metadata.exercise_number",
                    match=models.MatchValue(value=request.exercise_number),
                )
            )

        if not must:
            return []

        result = await self.qdrant_client.scroll(
            collection_name=self.collection_name,
            scroll_filter=models.Filter(must=must),
            limit=request.top_k,
            with_payload=True,
            with_vectors=False,
        )
        points = result[0] if isinstance(result, tuple) else result
        return [self._record_from_point(point, score=1.0) for point in points]

    async def semantic_search(self, request: RetrievalRequest) -> list[RetrievedRecord]:
        retriever = self.index.as_retriever(similarity_top_k=request.top_k)
        nodes = await retriever.aretrieve(request.query)
        records: list[RetrievedRecord] = []
        for node_with_score in nodes:
            node = node_with_score.node
            metadata = dict(node.metadata or {})
            records.append(
                RetrievedRecord(
                    text=node.get_content(),
                    filename=str(metadata.get("filename", "document.pdf")),
                    page_number=int(metadata.get("page_number", 0) or 0),
                    score=node_with_score.score,
                    doc_id=str(metadata.get("doc_id", "")),
                    block_id=str(metadata.get("block_id", "")),
                    block_type=_block_type_from_metadata(metadata.get("block_type", "unknown")),
                    exercise_number=str(metadata.get("exercise_number", "")),
                    section_title=str(metadata.get("section_title", "")),
                    visual_refs=tuple(metadata.get("visual_refs", []) or []),
                )
            )
        return records

    def _record_from_point(self, point: Any, *, score: float | None) -> RetrievedRecord:
        payload = getattr(point, "payload", None) or {}
        metadata = payload.get("metadata", payload)
        text = payload.get("_node_content") or payload.get("text") or payload.get("document", "")
        return RetrievedRecord(
            text=str(text),
            filename=str(metadata.get("filename", "document.pdf")),
            page_number=int(metadata.get("page_number", 0) or 0),
            score=score,
            doc_id=str(metadata.get("doc_id", "")),
            block_id=str(metadata.get("block_id", "")),
            block_type=_block_type_from_metadata(metadata.get("block_type", "unknown")),
            exercise_number=str(metadata.get("exercise_number", "")),
            section_title=str(metadata.get("section_title", "")),
            visual_refs=tuple(metadata.get("visual_refs", []) or []),
        )
