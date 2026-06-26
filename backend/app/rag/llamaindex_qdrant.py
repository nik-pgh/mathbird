"""Concrete Retriever backed by LlamaParse, LlamaIndex, and Qdrant."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from opentelemetry import trace

from app.config import Settings
from app.rag.formatter import format_records_as_chunks
from app.rag.indexing import parsed_document_to_nodes
from app.rag.parsing import BlockType, RetrievalRequest, RetrievedRecord, TextbookParser
from app.rag.query_parser import parse_retrieval_query
from app.rag.retriever import RetrievedChunk

# Phoenix / Arize OpenInference semantic-convention attribute keys. Used as
# literal strings so we don't pull the optional ``openinference`` package
# into the core code path. When Phoenix is disabled, ``trace.get_tracer``
# returns a NoOp tracer and these calls cost ~nothing. When Phoenix is on,
# spans emitted here show up alongside ``VectorIndexRetriever.aretrieve``
# in the UI under kind=RETRIEVER, so structured-lookup turns and semantic
# turns can be compared side-by-side.
_OI_SPAN_KIND = "openinference.span.kind"
_OI_INPUT_VALUE = "input.value"
_OI_OUTPUT_VALUE = "output.value"

_tracer = trace.get_tracer("mathbird.rag")

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
# Scroll returns points in arbitrary order; fetch more than top_k and rank
# heuristically before trimming (see ``_rank_structured_records``).
_STRUCTURED_SCROLL_OVERSCAN = 32
_STRUCTURED_SCROLL_MAX = 256

# Lower rank = preferred for page/section structured lookups.
_BLOCK_RANK_PAGE: dict[str, int] = {
    "heading": 0,
    "paragraph": 1,
    "instruction": 2,
    "example": 3,
    "unknown": 4,
    "table": 5,
    "exercise": 6,
    "image": 7,
    "graph": 8,
    "equation": 9,
}
_BLOCK_RANK_SECTION: dict[str, int] = {
    "heading": 0,
    "paragraph": 1,
    "example": 2,
    "instruction": 3,
    "unknown": 4,
    "table": 5,
    "exercise": 6,
    "image": 7,
    "graph": 8,
    "equation": 9,
}

QDRANT_PAYLOAD_INDEXES: tuple[tuple[str, str], ...] = (
    ("page_number", "integer"),
    ("printed_page_number", "integer"),
    ("chapter_number", "integer"),
    ("section_number", "keyword"),
    ("exercise_number", "keyword"),
    ("example_number", "keyword"),
    ("figure_number", "keyword"),
    ("equation_number", "keyword"),
    ("textbook_doc_id", "keyword"),
)


def _annotate_retrieved_documents(span: Any, records: list[RetrievedRecord]) -> None:
    """Attach OpenInference-formatted document attributes to a retrieval span.

    Mirrors the schema LlamaIndexInstrumentor emits for
    ``VectorIndexRetriever.aretrieve`` spans so the Phoenix UI renders
    structured-lookup turns next to semantic-search turns under the same
    kind=RETRIEVER view (with full content / score / metadata).
    """
    span.set_attribute("retrieval.documents.count", len(records))
    for i, rec in enumerate(records):
        prefix = f"retrieval.documents.{i}.document"
        if rec.block_id:
            span.set_attribute(f"{prefix}.id", rec.block_id)
        span.set_attribute(f"{prefix}.content", rec.text)
        if rec.score is not None:
            span.set_attribute(f"{prefix}.score", rec.score)
        # Metadata mirrors what LlamaIndexInstrumentor produces — keep the
        # key set identical so cross-filter ("kind=RETRIEVER AND ex#=2")
        # works uniformly.
        meta = f"{prefix}.metadata"
        span.set_attribute(f"{meta}.filename", rec.filename)
        span.set_attribute(f"{meta}.page_number", rec.page_number)
        span.set_attribute(f"{meta}.block_type", rec.block_type)
        if rec.exercise_number:
            span.set_attribute(f"{meta}.exercise_number", rec.exercise_number)
        if rec.example_number:
            span.set_attribute(f"{meta}.example_number", rec.example_number)
        if rec.section_number:
            span.set_attribute(f"{meta}.section_number", rec.section_number)
        if rec.figure_number:
            span.set_attribute(f"{meta}.figure_number", rec.figure_number)
        if rec.equation_number:
            span.set_attribute(f"{meta}.equation_number", rec.equation_number)
        if rec.section_title:
            span.set_attribute(f"{meta}.section_title", rec.section_title)
        if rec.chapter_number:
            span.set_attribute(f"{meta}.chapter_number", rec.chapter_number)
        if rec.doc_id:
            span.set_attribute(f"{meta}.textbook_doc_id", rec.doc_id)


def _block_type_from_metadata(value: Any) -> BlockType:
    block_type = str(value or "unknown")
    if block_type not in VALID_BLOCK_TYPES:
        return "unknown"
    return cast(BlockType, block_type)


def _structured_scroll_limit(top_k: int) -> int:
    return min(max(top_k * 8, _STRUCTURED_SCROLL_OVERSCAN), _STRUCTURED_SCROLL_MAX)


def _effective_page(record: RetrievedRecord) -> int:
    if record.printed_page_number:
        return record.printed_page_number
    return record.page_number


def _block_index(record: RetrievedRecord) -> int:
    block_id = record.block_id
    if not block_id:
        return 0
    parts = block_id.rsplit(":b", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return int(parts[1])
    return 0


def _block_type_rank(block_type: BlockType, ranking: dict[str, int]) -> int:
    return ranking.get(block_type, 50)


def _structured_sort_key(record: RetrievedRecord, request: RetrievalRequest) -> tuple[int, ...]:
    page = _effective_page(record)
    block_idx = _block_index(record)

    if request.page_number is not None:
        return (_block_type_rank(record.block_type, _BLOCK_RANK_PAGE), page, block_idx)
    if request.chapter_number is not None:
        return (page, block_idx)
    if request.section_number:
        return (
            page,
            _block_type_rank(record.block_type, _BLOCK_RANK_SECTION),
            block_idx,
        )
    if request.equation_number:
        eq_rank = 0 if record.block_type == "equation" else 1
        return (eq_rank, page, block_idx)
    if request.figure_number:
        visual_rank = 0 if record.block_type in ("image", "graph") else 1
        return (visual_rank, page, block_idx)
    return (page, block_idx)


def _rank_structured_records(
    records: list[RetrievedRecord],
    request: RetrievalRequest,
) -> list[RetrievedRecord]:
    ranked = sorted(records, key=lambda record: _structured_sort_key(record, request))
    return ranked[: request.top_k]


def _record_from_metadata(
    metadata: dict[str, Any],
    *,
    text: str,
    score: float | None,
) -> RetrievedRecord:
    return RetrievedRecord(
        text=str(text),
        filename=str(metadata.get("filename", "document.pdf")),
        page_number=int(metadata.get("page_number", 0) or 0),
        printed_page_number=int(metadata.get("printed_page_number", 0) or 0),
        score=score,
        doc_id=str(metadata.get("textbook_doc_id") or metadata.get("doc_id", "")),
        block_id=str(metadata.get("block_id", "")),
        block_type=_block_type_from_metadata(metadata.get("block_type", "unknown")),
        exercise_number=str(metadata.get("exercise_number", "")),
        example_number=str(metadata.get("example_number", "")),
        figure_number=str(metadata.get("figure_number", "")),
        equation_number=str(metadata.get("equation_number", "")),
        section_number=str(metadata.get("section_number", "")),
        section_title=str(metadata.get("section_title", "")),
        chapter_number=int(metadata.get("chapter_number", 0) or 0),
        visual_refs=tuple(metadata.get("visual_refs", []) or []),
    )


@dataclass(frozen=True)
class QdrantIndexStack:
    index: Any
    store: QdrantTextbookStore
    collection_name: str
    qdrant_client: Any


def build_qdrant_index_stack(settings: Settings) -> QdrantIndexStack:
    """Wire LlamaIndex + Qdrant for one embedding provider/model pair."""
    from llama_index.core import StorageContext, VectorStoreIndex
    from llama_index.vector_stores.qdrant import QdrantVectorStore
    from qdrant_client import AsyncQdrantClient

    from app.rag.embeddings import build_embed_model

    collection_name = settings.resolved_qdrant_collection
    qdrant_client = AsyncQdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
    )
    vector_store = QdrantVectorStore(
        aclient=qdrant_client,
        collection_name=collection_name,
    )
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    embed_model = build_embed_model(settings)
    index = VectorStoreIndex.from_vector_store(
        vector_store=vector_store,
        storage_context=storage_context,
        embed_model=embed_model,
    )
    store = QdrantTextbookStore(
        qdrant_client=qdrant_client,
        collection_name=collection_name,
        index=index,
    )
    return QdrantIndexStack(
        index=index,
        store=store,
        collection_name=collection_name,
        qdrant_client=qdrant_client,
    )


async def close_qdrant_client(client: Any) -> None:
    close = getattr(client, "close", None)
    if close is None:
        return
    result = close()
    if hasattr(result, "__await__"):
        await result


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
        await self.ingest_nodes(nodes)

    async def ingest_nodes(self, nodes: list[Any]) -> None:
        if not nodes:
            return
        # Insert first so LlamaIndex creates the Qdrant collection with the
        # right vector params if it doesn't exist yet. Payload indexes are
        # then applied — Qdrant indexes existing points retroactively, so
        # this order is correct on both fresh and pre-existing collections.
        await self.index.ainsert_nodes(nodes)
        ensure_indexes = getattr(self.store, "ensure_payload_indexes", None)
        if ensure_indexes is not None:
            await ensure_indexes()

    async def retrieve(
        self,
        query: str,
        *,
        top_k: int = 4,
        doc_ids: tuple[str, ...] = (),
    ) -> list[RetrievedChunk]:
        parsed = parse_retrieval_query(query)
        request = RetrievalRequest(
            query=query,
            top_k=top_k,
            doc_ids=doc_ids,
            page_number=parsed.page_number,
            chapter_number=parsed.chapter_number,
            section_number=parsed.section_number,
            exercise_number=parsed.exercise_number,
            example_number=parsed.example_number,
            figure_number=parsed.figure_number,
            equation_number=parsed.equation_number,
        )

        if parsed.is_structured_lookup:
            records = await self.store.structured_lookup(request)
            chunks = format_records_as_chunks(records)
            if chunks:
                return chunks

        records = await self.store.semantic_search(request)
        return format_records_as_chunks(records)


class QdrantTextbookStore:
    def __init__(self, *, qdrant_client: Any, collection_name: str, index: Any) -> None:
        self.qdrant_client = qdrant_client
        self.collection_name = collection_name
        self.index = index
        self._payload_indexes_ready = False

    async def ensure_payload_indexes(self) -> None:
        if self._payload_indexes_ready:
            return

        from qdrant_client.http import models
        from qdrant_client.http.exceptions import UnexpectedResponse

        schema_by_name = {
            "integer": models.PayloadSchemaType.INTEGER,
            "keyword": models.PayloadSchemaType.KEYWORD,
        }
        for field_name, schema_name in QDRANT_PAYLOAD_INDEXES:
            try:
                await self.qdrant_client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field_name,
                    field_schema=schema_by_name[schema_name],
                )
            except UnexpectedResponse as exc:
                if "already exists" not in str(exc).lower():
                    raise

        self._payload_indexes_ready = True

    async def structured_lookup(self, request: RetrievalRequest) -> list[RetrievedRecord]:
        with _tracer.start_as_current_span("structured_lookup") as span:
            span.set_attribute(_OI_SPAN_KIND, "RETRIEVER")
            span.set_attribute(_OI_INPUT_VALUE, request.query)
            if request.page_number is not None:
                span.set_attribute("filter.page_number", request.page_number)
            if request.chapter_number is not None:
                span.set_attribute("filter.chapter_number", request.chapter_number)
            if request.exercise_number:
                span.set_attribute("filter.exercise_number", request.exercise_number)
            if request.example_number:
                span.set_attribute("filter.example_number", request.example_number)
            if request.section_number:
                span.set_attribute("filter.section_number", request.section_number)
            if request.figure_number:
                span.set_attribute("filter.figure_number", request.figure_number)
            if request.equation_number:
                span.set_attribute("filter.equation_number", request.equation_number)
            if request.doc_ids:
                span.set_attribute("filter.doc_ids", list(request.doc_ids))

            records = await self._do_structured_lookup(request)
            _annotate_retrieved_documents(span, records)
            return records

    async def _do_structured_lookup(self, request: RetrievalRequest) -> list[RetrievedRecord]:
        await self.ensure_payload_indexes()

        from qdrant_client.http import models

        must: list[Any] = []
        if request.page_number is not None:
            page = request.page_number
            must.append(
                models.Filter(
                    should=[
                        models.FieldCondition(
                            key="page_number",
                            match=models.MatchValue(value=page),
                        ),
                        models.FieldCondition(
                            key="printed_page_number",
                            match=models.MatchValue(value=page),
                        ),
                    ]
                )
            )
        if request.chapter_number is not None:
            must.append(
                models.FieldCondition(
                    key="chapter_number",
                    match=models.MatchValue(value=request.chapter_number),
                )
            )
        if request.section_number:
            must.append(
                models.FieldCondition(
                    key="section_number",
                    match=models.MatchValue(value=request.section_number),
                )
            )
        if request.exercise_number:
            must.append(
                models.FieldCondition(
                    key="exercise_number",
                    match=models.MatchValue(value=request.exercise_number),
                )
            )
        if request.example_number:
            must.append(
                models.FieldCondition(
                    key="example_number",
                    match=models.MatchValue(value=request.example_number),
                )
            )
        if request.figure_number:
            must.append(
                models.FieldCondition(
                    key="figure_number",
                    match=models.MatchValue(value=request.figure_number),
                )
            )
        if request.equation_number:
            must.append(
                models.FieldCondition(
                    key="equation_number",
                    match=models.MatchValue(value=request.equation_number),
                )
            )
        if request.doc_ids:
            if len(request.doc_ids) == 1:
                match = models.MatchValue(value=request.doc_ids[0])
            else:
                match = models.MatchAny(any=list(request.doc_ids))
            must.append(models.FieldCondition(key="textbook_doc_id", match=match))

        if not must:
            return []

        scroll_limit = _structured_scroll_limit(request.top_k)
        result = await self.qdrant_client.scroll(
            collection_name=self.collection_name,
            scroll_filter=models.Filter(must=must),
            limit=scroll_limit,
            with_payload=True,
            with_vectors=False,
        )
        points = result[0] if isinstance(result, tuple) else result
        records = [self._record_from_point(point, score=1.0) for point in points]
        return _rank_structured_records(records, request)

    async def semantic_search(self, request: RetrievalRequest) -> list[RetrievedRecord]:
        retriever_kwargs: dict[str, Any] = {"similarity_top_k": request.top_k}
        if request.doc_ids:
            from llama_index.core.vector_stores import (
                FilterOperator,
                MetadataFilter,
                MetadataFilters,
            )

            operator = FilterOperator.EQ if len(request.doc_ids) == 1 else FilterOperator.IN
            value: str | list[str] = (
                request.doc_ids[0] if len(request.doc_ids) == 1 else list(request.doc_ids)
            )
            retriever_kwargs["filters"] = MetadataFilters(
                filters=[
                    MetadataFilter(
                        key="textbook_doc_id",
                        value=value,
                        operator=operator,
                    )
                ]
            )

        retriever = self.index.as_retriever(**retriever_kwargs)
        nodes = await retriever.aretrieve(request.query)
        records: list[RetrievedRecord] = []
        for node_with_score in nodes:
            node = node_with_score.node
            metadata = dict(node.metadata or {})
            records.append(
                _record_from_metadata(
                    metadata,
                    text=node.get_content(),
                    score=node_with_score.score,
                )
            )
        return records

    def _record_from_point(self, point: Any, *, score: float | None) -> RetrievedRecord:
        payload = getattr(point, "payload", None) or {}
        node = self._node_from_payload(payload)
        if node is not None:
            metadata = dict(node.metadata or {})
            text = node.get_content()
        else:
            metadata = payload.get("metadata", payload)
            text = payload.get("text") or payload.get("document", "")
        return _record_from_metadata(metadata, text=str(text), score=score)

    def _node_from_payload(self, payload: dict[str, Any]) -> Any | None:
        if not payload.get("_node_content"):
            return None

        from llama_index.core.vector_stores.utils import metadata_dict_to_node

        try:
            return metadata_dict_to_node(payload)
        except Exception:
            return None
