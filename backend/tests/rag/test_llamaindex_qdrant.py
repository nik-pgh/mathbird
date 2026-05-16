import json
from types import SimpleNamespace

import pytest
from llama_index.core.vector_stores.utils import node_to_metadata_dict

from app.rag.indexing import parsed_document_to_nodes
from app.rag.llamaindex_qdrant import LlamaIndexQdrantRetriever, QdrantTextbookStore
from app.rag.parsing import (
    ParsedBlock,
    ParsedDocument,
    ParsedPage,
    RetrievalRequest,
    RetrievedRecord,
)


class FakeParser:
    async def parse_pdf(self, path, *, doc_id, filename):
        return ParsedDocument(
            doc_id=doc_id,
            filename=filename,
            pages=[
                ParsedPage(
                    page_number=37,
                    text="",
                    blocks=[
                        ParsedBlock(
                            block_id=f"{doc_id}:p37:b0",
                            page_number=37,
                            block_type="exercise",
                            text="Problem 8. Solve 2x + 3 = 9.",
                            markdown="Problem 8. Solve 2x + 3 = 9.",
                            exercise_number="8",
                        )
                    ],
                )
            ],
        )


class FakeIndex:
    def __init__(self) -> None:
        self.inserted = []

    async def ainsert_nodes(self, nodes):
        self.inserted.extend(nodes)


class FakeStore:
    def __init__(self) -> None:
        self.structured_requests = []
        self.records = [
            RetrievedRecord(
                text="Problem 8. Solve 2x + 3 = 9.",
                filename="book.pdf",
                page_number=37,
                block_type="exercise",
                exercise_number="8",
                block_id="doc-1:p37:b0",
                score=1.0,
            )
        ]

    async def structured_lookup(self, request):
        self.structured_requests.append(request)
        return self.records

    async def semantic_search(self, request):
        return self.records


class ExampleStore:
    def __init__(self) -> None:
        self.structured_requests = []
        self.records = [
            RetrievedRecord(
                text="Example 3. Factor x^2 + 5x + 6.",
                filename="book.pdf",
                page_number=20,
                block_type="example",
                example_number="3",
                block_id="doc-1:p20:b0",
                score=1.0,
            )
        ]

    async def structured_lookup(self, request):
        self.structured_requests.append(request)
        return self.records

    async def semantic_search(self, request):
        return []


class EmptyStructuredStore:
    async def structured_lookup(self, request):
        return [
            RetrievedRecord(
                text="",
                filename="book.pdf",
                page_number=37,
                block_type="exercise",
                exercise_number="8",
                block_id="empty-structured",
                score=1.0,
            )
        ]

    async def semantic_search(self, request):
        return [
            RetrievedRecord(
                text="Semantic fallback result.",
                filename="book.pdf",
                page_number=38,
                block_type="paragraph",
                block_id="semantic-result",
                score=0.7,
            )
        ]


class FakeQdrantClient:
    def __init__(self, points) -> None:
        self.points = points
        self.scroll_calls = []

    async def scroll(self, **kwargs):
        self.scroll_calls.append(kwargs)
        return self.points, None


class FakeNode:
    def __init__(self, text: str, metadata: dict) -> None:
        self.metadata = metadata
        self._text = text

    def get_content(self) -> str:
        return self._text


class FakeLlamaIndexRetriever:
    def __init__(self, nodes) -> None:
        self.nodes = nodes

    async def aretrieve(self, query):
        return self.nodes


class SemanticFilterIndex:
    def __init__(self) -> None:
        self.as_retriever_calls = []

    def as_retriever(self, **kwargs):
        self.as_retriever_calls.append(kwargs)
        return FakeLlamaIndexRetriever(
            [
                SimpleNamespace(
                    node=FakeNode(
                        "Scoped semantic result.",
                        {
                            "filename": "book.pdf",
                            "page_number": 5,
                            "textbook_doc_id": "doc-1",
                            "block_id": "doc-1:p5:b0",
                            "block_type": "paragraph",
                        },
                    ),
                    score=0.5,
                )
            ]
        )


def textbook_payload(*, block_type: str = "exercise") -> dict:
    document = ParsedDocument(
        doc_id="textbook-doc",
        filename="book.pdf",
        pages=[
            ParsedPage(
                page_number=37,
                text="",
                blocks=[
                    ParsedBlock(
                        block_id="textbook-doc:p37:b0",
                        page_number=37,
                        block_type="exercise",
                        text="Problem 8. Solve 2x + 3 = 9.",
                        markdown="Problem 8. Solve 2x + 3 = 9.",
                        exercise_number="8",
                    )
                ],
            )
        ],
    )
    node = parsed_document_to_nodes(document)[0]
    payload = node_to_metadata_dict(node, remove_text=False, flat_metadata=False)
    node_content = json.loads(payload["_node_content"])
    node_content["metadata"]["block_type"] = block_type
    payload["_node_content"] = json.dumps(node_content)
    return payload


def example_payload() -> dict:
    document = ParsedDocument(
        doc_id="textbook-doc",
        filename="book.pdf",
        pages=[
            ParsedPage(
                page_number=20,
                text="",
                blocks=[
                    ParsedBlock(
                        block_id="textbook-doc:p20:b0",
                        page_number=20,
                        block_type="example",
                        text="Example 3. Factor x^2 + 5x + 6.",
                        markdown="Example 3. Factor x^2 + 5x + 6.",
                        example_number="3",
                    )
                ],
            )
        ],
    )
    node = parsed_document_to_nodes(document)[0]
    return node_to_metadata_dict(node, remove_text=False, flat_metadata=False)


@pytest.mark.asyncio
async def test_ingest_pdf_parses_and_inserts_nodes(tmp_path) -> None:
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.7")
    index = FakeIndex()
    retriever = LlamaIndexQdrantRetriever(
        parser=FakeParser(),
        index=index,
        store=FakeStore(),
        filename_resolver=lambda path: "book.pdf",
    )

    await retriever.ingest_pdf(str(pdf), doc_id="doc-1")

    assert len(index.inserted) == 1
    assert index.inserted[0].metadata["exercise_number"] == "8"


@pytest.mark.asyncio
async def test_retrieve_uses_structured_lookup_for_page_problem_query() -> None:
    store = FakeStore()
    retriever = LlamaIndexQdrantRetriever(
        parser=FakeParser(),
        index=FakeIndex(),
        store=store,
        filename_resolver=lambda path: "book.pdf",
    )

    chunks = await retriever.retrieve(
        "help me with problem 8 on page 37",
        top_k=4,
        doc_ids=("doc-1",),
    )

    assert store.structured_requests[0].doc_ids == ("doc-1",)
    assert chunks[0].source == "book.pdf, page 37, problem 8"
    assert chunks[0].text == "Problem 8. Solve 2x + 3 = 9."


@pytest.mark.asyncio
async def test_retrieve_passes_example_number_to_structured_lookup_and_formats_source() -> None:
    store = ExampleStore()
    retriever = LlamaIndexQdrantRetriever(
        parser=FakeParser(),
        index=FakeIndex(),
        store=store,
        filename_resolver=lambda path: "book.pdf",
    )

    chunks = await retriever.retrieve("explain example 3 on page 20", top_k=4)

    assert store.structured_requests[0].page_number == 20
    assert store.structured_requests[0].example_number == "3"
    assert chunks[0].source == "book.pdf, page 20, example 3"
    assert chunks[0].text == "Example 3. Factor x^2 + 5x + 6."


@pytest.mark.asyncio
async def test_retrieve_falls_back_to_semantic_when_structured_records_format_empty() -> None:
    retriever = LlamaIndexQdrantRetriever(
        parser=FakeParser(),
        index=FakeIndex(),
        store=EmptyStructuredStore(),
        filename_resolver=lambda path: "book.pdf",
    )

    chunks = await retriever.retrieve("help me with problem 8 on page 37", top_k=4)

    assert len(chunks) == 1
    assert chunks[0].text == "Semantic fallback result."
    assert chunks[0].source == "book.pdf, page 38"


@pytest.mark.asyncio
async def test_structured_lookup_uses_top_level_qdrant_filter_keys() -> None:
    point = SimpleNamespace(payload=textbook_payload())
    qdrant_client = FakeQdrantClient(points=[point])
    store = QdrantTextbookStore(
        qdrant_client=qdrant_client,
        collection_name="textbook_chunks",
        index=FakeIndex(),
    )

    await store.structured_lookup(
        request=RetrievalRequest(
            query="problem 8 page 37",
            top_k=4,
            page_number=37,
            exercise_number="8",
        )
    )

    filter_conditions = qdrant_client.scroll_calls[0]["scroll_filter"].must
    assert [condition.key for condition in filter_conditions] == ["page_number", "exercise_number"]


@pytest.mark.asyncio
async def test_structured_lookup_filters_by_example_number() -> None:
    point = SimpleNamespace(payload=example_payload())
    qdrant_client = FakeQdrantClient(points=[point])
    store = QdrantTextbookStore(
        qdrant_client=qdrant_client,
        collection_name="textbook_chunks",
        index=FakeIndex(),
    )

    records = await store.structured_lookup(
        request=RetrievalRequest(
            query="example 3 page 20",
            top_k=4,
            page_number=20,
            example_number="3",
        )
    )

    filter_conditions = qdrant_client.scroll_calls[0]["scroll_filter"].must
    assert [condition.key for condition in filter_conditions] == ["page_number", "example_number"]
    assert records[0].source == "book.pdf, page 20, example 3"


@pytest.mark.asyncio
async def test_structured_lookup_filters_by_textbook_doc_id() -> None:
    point = SimpleNamespace(payload=textbook_payload())
    qdrant_client = FakeQdrantClient(points=[point])
    store = QdrantTextbookStore(
        qdrant_client=qdrant_client,
        collection_name="textbook_chunks",
        index=FakeIndex(),
    )

    await store.structured_lookup(
        request=RetrievalRequest(
            query="problem 8 page 37",
            top_k=4,
            doc_ids=("textbook-doc",),
            page_number=37,
            exercise_number="8",
        )
    )

    filter_conditions = qdrant_client.scroll_calls[0]["scroll_filter"].must
    assert [condition.key for condition in filter_conditions] == [
        "page_number",
        "exercise_number",
        "textbook_doc_id",
    ]
    assert filter_conditions[-1].match.value == "textbook-doc"


@pytest.mark.asyncio
async def test_structured_lookup_decodes_node_content_and_original_metadata() -> None:
    point = SimpleNamespace(payload=textbook_payload(block_type="worked-problem"))
    store = QdrantTextbookStore(
        qdrant_client=FakeQdrantClient(points=[point]),
        collection_name="textbook_chunks",
        index=FakeIndex(),
    )

    records = await store.structured_lookup(
        request=RetrievalRequest(
            query="problem 8 page 37",
            top_k=4,
            page_number=37,
            exercise_number="8",
        )
    )

    assert records[0].text == "Problem 8. Solve 2x + 3 = 9."
    assert not records[0].text.startswith("{")
    assert records[0].doc_id == "textbook-doc"
    assert records[0].block_type == "unknown"


@pytest.mark.asyncio
async def test_semantic_search_applies_textbook_doc_id_filter() -> None:
    index = SemanticFilterIndex()
    store = QdrantTextbookStore(
        qdrant_client=FakeQdrantClient(points=[]),
        collection_name="textbook_chunks",
        index=index,
    )

    records = await store.semantic_search(
        RetrievalRequest(query="linear equations", top_k=4, doc_ids=("doc-1",))
    )

    filters = index.as_retriever_calls[0]["filters"].filters
    assert index.as_retriever_calls[0]["similarity_top_k"] == 4
    assert filters[0].key == "textbook_doc_id"
    assert filters[0].value == "doc-1"
    assert records[0].doc_id == "doc-1"
