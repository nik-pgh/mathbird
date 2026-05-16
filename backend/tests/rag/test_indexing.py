from app.rag.indexing import parsed_document_to_nodes
from app.rag.parsing import ParsedBlock, ParsedDocument, ParsedPage


def test_parsed_document_to_nodes_preserves_metadata() -> None:
    doc = ParsedDocument(
        doc_id="doc-1",
        filename="book.pdf",
        pages=[
            ParsedPage(
                page_number=37,
                text="",
                blocks=[
                    ParsedBlock(
                        block_id="doc-1:p37:b0",
                        page_number=37,
                        block_type="example",
                        text="Example 8. Solve 2x + 3 = 9.",
                        markdown="Example 8. Solve 2x + 3 = 9.",
                        example_number="8",
                        section_title="Solving Equations",
                        neighboring_block_ids=("doc-1:p37:b-1",),
                    )
                ],
            )
        ],
    )

    nodes = parsed_document_to_nodes(doc)

    assert len(nodes) == 1
    assert nodes[0].text == "Example 8. Solve 2x + 3 = 9."
    assert nodes[0].metadata["doc_id"] == "doc-1"
    assert nodes[0].metadata["textbook_doc_id"] == "doc-1"
    assert nodes[0].metadata["page_number"] == 37
    assert nodes[0].metadata["block_type"] == "example"
    assert nodes[0].metadata["example_number"] == "8"
    assert nodes[0].metadata["neighboring_block_ids"] == ["doc-1:p37:b-1"]
