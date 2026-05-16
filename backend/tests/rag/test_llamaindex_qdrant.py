import pytest

from app.rag.llamaindex_qdrant import LlamaIndexQdrantRetriever
from app.rag.parsing import ParsedBlock, ParsedDocument, ParsedPage, RetrievedRecord


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
        return self.records

    async def semantic_search(self, request):
        return self.records


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
    retriever = LlamaIndexQdrantRetriever(
        parser=FakeParser(),
        index=FakeIndex(),
        store=FakeStore(),
        filename_resolver=lambda path: "book.pdf",
    )

    chunks = await retriever.retrieve("help me with problem 8 on page 37", top_k=4)

    assert chunks[0].source == "book.pdf, page 37, problem 8"
    assert chunks[0].text == "Problem 8. Solve 2x + 3 = 9."
