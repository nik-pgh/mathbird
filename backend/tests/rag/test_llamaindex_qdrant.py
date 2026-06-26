import json
from types import SimpleNamespace

import pytest
from llama_index.core.vector_stores.utils import node_to_metadata_dict

from app.rag.indexing import parsed_document_to_nodes
from app.rag.llamaindex_qdrant import (
    LlamaIndexQdrantRetriever,
    QdrantTextbookStore,
    _structured_scroll_limit,
)
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
        self.ensure_payload_indexes_calls = 0

    async def ensure_payload_indexes(self):
        self.ensure_payload_indexes_calls += 1

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
        self.create_payload_index_calls = []

    async def scroll(self, **kwargs):
        self.scroll_calls.append(kwargs)
        return self.points, None

    async def create_payload_index(self, **kwargs):
        self.create_payload_index_calls.append(kwargs)
        return None


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
                        chapter_number=2,
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


def chapter_payload() -> dict:
    document = ParsedDocument(
        doc_id="textbook-doc",
        filename="deep_learning_ch2.pdf",
        pages=[
            ParsedPage(
                page_number=8,
                text="",
                blocks=[
                    ParsedBlock(
                        block_id="textbook-doc:p8:b0",
                        page_number=8,
                        block_type="paragraph",
                        text="Sometimes we need to measure the size of a vector.",
                        markdown="Sometimes we need to measure the size of a vector.",
                        chapter_number=2,
                    )
                ],
            )
        ],
    )
    node = parsed_document_to_nodes(document)[0]
    return node_to_metadata_dict(node, remove_text=False, flat_metadata=False)


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
    store = FakeStore()
    retriever = LlamaIndexQdrantRetriever(
        parser=FakeParser(),
        index=index,
        store=store,
        filename_resolver=lambda path: "book.pdf",
    )

    await retriever.ingest_pdf(str(pdf), doc_id="doc-1")

    assert len(index.inserted) == 1
    assert index.inserted[0].metadata["exercise_number"] == "8"
    assert store.ensure_payload_indexes_calls == 1


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
    page_filter = filter_conditions[0]
    assert {condition.key for condition in page_filter.should} == {
        "page_number",
        "printed_page_number",
    }
    assert filter_conditions[1].key == "exercise_number"


@pytest.mark.asyncio
async def test_structured_lookup_creates_required_qdrant_payload_indexes() -> None:
    qdrant_client = FakeQdrantClient(points=[])
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

    assert [
        (call["field_name"], call["field_schema"].value)
        for call in qdrant_client.create_payload_index_calls
    ] == [
        ("page_number", "integer"),
        ("printed_page_number", "integer"),
        ("chapter_number", "integer"),
        ("section_number", "keyword"),
        ("exercise_number", "keyword"),
        ("example_number", "keyword"),
        ("figure_number", "keyword"),
        ("equation_number", "keyword"),
        ("textbook_doc_id", "keyword"),
    ]


@pytest.mark.asyncio
async def test_structured_lookup_filters_by_chapter_number() -> None:
    point = SimpleNamespace(payload=chapter_payload())
    qdrant_client = FakeQdrantClient(points=[point])
    store = QdrantTextbookStore(
        qdrant_client=qdrant_client,
        collection_name="textbook_chunks",
        index=FakeIndex(),
    )

    records = await store.structured_lookup(
        request=RetrievalRequest(
            query="chapter 2",
            top_k=4,
            chapter_number=2,
        )
    )

    filter_conditions = qdrant_client.scroll_calls[0]["scroll_filter"].must
    assert [condition.key for condition in filter_conditions] == ["chapter_number"]
    assert records[0].source == "deep_learning_ch2.pdf, chapter 2, page 8"
    assert records[0].chapter_number == 2


@pytest.mark.asyncio
async def test_retrieve_passes_chapter_number_to_structured_lookup() -> None:
    store = FakeStore()
    store.records = [
        RetrievedRecord(
            text="Linear algebra basics.",
            filename="book.pdf",
            page_number=1,
            block_type="paragraph",
            chapter_number=2,
            block_id="doc-1:p1:b0",
            score=1.0,
        )
    ]
    retriever = LlamaIndexQdrantRetriever(
        parser=FakeParser(),
        index=FakeIndex(),
        store=store,
        filename_resolver=lambda path: "book.pdf",
    )

    chunks = await retriever.retrieve("chapter 2 linear algebra", top_k=4)

    assert store.structured_requests[0].chapter_number == 2
    assert chunks[0].source == "book.pdf, chapter 2, page 1"


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
    page_filter = filter_conditions[0]
    assert {condition.key for condition in page_filter.should} == {
        "page_number",
        "printed_page_number",
    }
    assert filter_conditions[1].key == "example_number"
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
    page_filter = filter_conditions[0]
    assert {condition.key for condition in page_filter.should} == {
        "page_number",
        "printed_page_number",
    }
    assert filter_conditions[1].key == "exercise_number"
    assert filter_conditions[2].key == "textbook_doc_id"
    assert filter_conditions[2].match.value == "textbook-doc"


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
async def test_structured_lookup_filters_by_section_number() -> None:
    document = ParsedDocument(
        doc_id="textbook-doc",
        filename="deep_learning_ch2.pdf",
        pages=[
            ParsedPage(
                page_number=12,
                printed_page_number=42,
                text="",
                blocks=[
                    ParsedBlock(
                        block_id="textbook-doc:p12:b0",
                        page_number=12,
                        printed_page_number=42,
                        block_type="paragraph",
                        text="An eigenvector is a nonzero vector v.",
                        section_number="2.7",
                        section_title="2.7 Eigendecomposition",
                        chapter_number=2,
                    )
                ],
            )
        ],
    )
    node = parsed_document_to_nodes(document)[0]
    payload = node_to_metadata_dict(node, remove_text=False, flat_metadata=False)
    point = SimpleNamespace(payload=payload)
    store = QdrantTextbookStore(
        qdrant_client=FakeQdrantClient(points=[point]),
        collection_name="textbook_chunks",
        index=FakeIndex(),
    )

    records = await store.structured_lookup(
        request=RetrievalRequest(
            query="section 2.7",
            top_k=4,
            section_number="2.7",
        )
    )

    filter_conditions = store.qdrant_client.scroll_calls[0]["scroll_filter"].must
    assert filter_conditions[0].key == "section_number"
    assert records[0].section_number == "2.7"
    assert records[0].source == "deep_learning_ch2.pdf, chapter 2, page 42, section 2.7"


@pytest.mark.asyncio
async def test_structured_lookup_matches_printed_page_number() -> None:
    document = ParsedDocument(
        doc_id="textbook-doc",
        filename="deep_learning_ch2.pdf",
        pages=[
            ParsedPage(
                page_number=14,
                printed_page_number=44,
                text="",
                blocks=[
                    ParsedBlock(
                        block_id="textbook-doc:p14:b0",
                        page_number=14,
                        printed_page_number=44,
                        block_type="paragraph",
                        text="A real symmetric matrix has an eigendecomposition.",
                        chapter_number=2,
                    )
                ],
            )
        ],
    )
    node = parsed_document_to_nodes(document)[0]
    payload = node_to_metadata_dict(node, remove_text=False, flat_metadata=False)
    point = SimpleNamespace(payload=payload)
    store = QdrantTextbookStore(
        qdrant_client=FakeQdrantClient(points=[point]),
        collection_name="textbook_chunks",
        index=FakeIndex(),
    )

    records = await store.structured_lookup(
        request=RetrievalRequest(
            query="page 44",
            top_k=4,
            page_number=44,
        )
    )

    assert len(records) == 1
    assert records[0].printed_page_number == 44
    assert records[0].source == "deep_learning_ch2.pdf, chapter 2, page 44"


def _points_from_page_blocks(
    blocks: list[ParsedBlock],
    *,
    page_number: int = 37,
    printed_page_number: int = 0,
) -> list[SimpleNamespace]:
    document = ParsedDocument(
        doc_id="textbook-doc",
        filename="deep_learning_ch2.pdf",
        pages=[
            ParsedPage(
                page_number=page_number,
                printed_page_number=printed_page_number or page_number,
                text="",
                blocks=blocks,
            )
        ],
    )
    nodes = parsed_document_to_nodes(document)
    return [
        SimpleNamespace(
            payload=node_to_metadata_dict(node, remove_text=False, flat_metadata=False)
        )
        for node in nodes
    ]


@pytest.mark.asyncio
async def test_structured_lookup_scroll_limit_overscans_top_k() -> None:
    store = QdrantTextbookStore(
        qdrant_client=FakeQdrantClient(points=[]),
        collection_name="textbook_chunks",
        index=FakeIndex(),
    )

    await store.structured_lookup(
        RetrievalRequest(query="page 37", top_k=4, page_number=37)
    )

    assert store.qdrant_client.scroll_calls[0]["limit"] == _structured_scroll_limit(4)


@pytest.mark.asyncio
async def test_structured_lookup_ranks_paragraph_before_equation_on_page_query() -> None:
    points = _points_from_page_blocks(
        [
            ParsedBlock(
                block_id="textbook-doc:p37:b0",
                page_number=37,
                printed_page_number=37,
                block_type="equation",
                text="A = Q \\Lambda Q^T",
                equation_number="2.77",
                chapter_number=2,
            ),
            ParsedBlock(
                block_id="textbook-doc:p37:b1",
                page_number=37,
                printed_page_number=37,
                block_type="paragraph",
                text="An eigenvector is a nonzero vector v.",
                chapter_number=2,
            ),
        ],
        page_number=37,
        printed_page_number=37,
    )
    store = QdrantTextbookStore(
        qdrant_client=FakeQdrantClient(points=list(reversed(points))),
        collection_name="textbook_chunks",
        index=FakeIndex(),
    )

    records = await store.structured_lookup(
        RetrievalRequest(query="page 37", top_k=2, page_number=37)
    )

    assert [record.block_type for record in records] == ["paragraph", "equation"]


@pytest.mark.asyncio
async def test_structured_lookup_ranks_heading_before_paragraph_on_section_query() -> None:
    points = _points_from_page_blocks(
        [
            ParsedBlock(
                block_id="textbook-doc:p12:b0",
                page_number=12,
                printed_page_number=42,
                block_type="paragraph",
                text="An eigenvector is a nonzero vector v.",
                section_number="2.7",
                section_title="2.7 Eigendecomposition",
                chapter_number=2,
            ),
            ParsedBlock(
                block_id="textbook-doc:p12:b1",
                page_number=12,
                printed_page_number=42,
                block_type="heading",
                text="2.7 Eigendecomposition",
                section_number="2.7",
                section_title="2.7 Eigendecomposition",
                chapter_number=2,
            ),
        ],
        page_number=12,
        printed_page_number=42,
    )
    store = QdrantTextbookStore(
        qdrant_client=FakeQdrantClient(points=points),
        collection_name="textbook_chunks",
        index=FakeIndex(),
    )

    records = await store.structured_lookup(
        RetrievalRequest(query="section 2.7", top_k=2, section_number="2.7")
    )

    assert [record.block_type for record in records] == ["heading", "paragraph"]


@pytest.mark.asyncio
async def test_structured_lookup_ranks_chapter_blocks_by_page() -> None:
    points = _points_from_page_blocks(
        [
            ParsedBlock(
                block_id="textbook-doc:p20:b0",
                page_number=20,
                printed_page_number=50,
                block_type="paragraph",
                text="Later chapter content.",
                chapter_number=2,
            ),
        ],
        page_number=20,
        printed_page_number=50,
    )
    points.extend(
        _points_from_page_blocks(
            [
                ParsedBlock(
                    block_id="textbook-doc:p10:b0",
                    page_number=10,
                    printed_page_number=40,
                    block_type="paragraph",
                    text="Earlier chapter content.",
                    chapter_number=2,
                ),
            ],
            page_number=10,
            printed_page_number=40,
        )
    )
    store = QdrantTextbookStore(
        qdrant_client=FakeQdrantClient(points=points),
        collection_name="textbook_chunks",
        index=FakeIndex(),
    )

    records = await store.structured_lookup(
        RetrievalRequest(query="chapter 2", top_k=2, chapter_number=2)
    )

    assert [record.printed_page_number for record in records] == [40, 50]


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
