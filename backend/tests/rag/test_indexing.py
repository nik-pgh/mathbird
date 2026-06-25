from app.rag.indexing import parsed_document_to_chunked_nodes, parsed_document_to_nodes
from app.rag.parsing import ParsedBlock, ParsedDocument, ParsedPage


def test_parsed_document_to_nodes_preserves_metadata() -> None:
    doc = ParsedDocument(
        doc_id="doc-1",
        filename="book.pdf",
        pages=[
            ParsedPage(
                page_number=37,
                printed_page_number=37,
                text="",
                blocks=[
                    ParsedBlock(
                        block_id="doc-1:p37:b0",
                        page_number=37,
                        printed_page_number=37,
                        block_type="example",
                        text="Example 8. Solve 2x + 3 = 9.",
                        markdown="Example 8. Solve 2x + 3 = 9.",
                        example_number="8",
                        chapter_number=2,
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
    assert nodes[0].metadata["chapter_number"] == 2
    assert nodes[0].metadata["printed_page_number"] == 37
    assert nodes[0].metadata["neighboring_block_ids"] == ["doc-1:p37:b-1"]


def test_parsed_document_to_nodes_uses_qdrant_valid_node_id() -> None:
    doc = ParsedDocument(
        doc_id="doc-1",
        filename="book.pdf",
        pages=[
            ParsedPage(
                page_number=1,
                text="",
                blocks=[
                    ParsedBlock(
                        block_id="doc-1:p1:b0",
                        page_number=1,
                        block_type="paragraph",
                        text="Intro text.",
                    )
                ],
            )
        ],
    )

    node = parsed_document_to_nodes(doc)[0]

    assert node.node_id == "ab6b0520-4e57-5a81-9021-9267cca20c20"
    assert node.metadata["block_id"] == "doc-1:p1:b0"


def _chunk_policy_doc() -> ParsedDocument:
    return ParsedDocument(
        doc_id="doc-1",
        filename="book.pdf",
        pages=[
            ParsedPage(
                page_number=4,
                text="",
                blocks=[
                    ParsedBlock(
                        block_id="doc-1:p4:b0",
                        page_number=4,
                        block_type="heading",
                        text="2.2 Multiplying Matrices and Vectors",
                        section_title="2.2 Multiplying Matrices and Vectors",
                        chapter_number=2,
                    ),
                    ParsedBlock(
                        block_id="doc-1:p4:b1",
                        page_number=4,
                        block_type="paragraph",
                        text="For matrix product AB to be defined, dimensions must align.",
                        section_title="2.2 Multiplying Matrices and Vectors",
                        chapter_number=2,
                        neighboring_block_ids=("doc-1:p4:b0",),
                    ),
                    ParsedBlock(
                        block_id="doc-1:p4:b2",
                        page_number=4,
                        block_type="equation",
                        text="C has shape m x p.",
                        markdown="$C = AB$ has shape $m \\times p$.",
                        latex="$C = AB$ has shape $m \\times p$.",
                        section_title="2.2 Multiplying Matrices and Vectors",
                        chapter_number=2,
                        neighboring_block_ids=("doc-1:p4:b1",),
                    ),
                    ParsedBlock(
                        block_id="doc-1:p4:b3",
                        page_number=4,
                        block_type="paragraph",
                        text="The entries are computed by summing over k.",
                        section_title="2.2 Multiplying Matrices and Vectors",
                        chapter_number=2,
                        neighboring_block_ids=("doc-1:p4:b2",),
                    ),
                    ParsedBlock(
                        block_id="doc-1:p4:b4",
                        page_number=4,
                        block_type="heading",
                        text="2.3 Identity and Inverse Matrices",
                        section_title="2.3 Identity and Inverse Matrices",
                        chapter_number=2,
                        neighboring_block_ids=("doc-1:p4:b3",),
                    ),
                    ParsedBlock(
                        block_id="doc-1:p4:b5",
                        page_number=4,
                        block_type="paragraph",
                        text="The identity matrix leaves vectors unchanged.",
                        section_title="2.3 Identity and Inverse Matrices",
                        chapter_number=2,
                        neighboring_block_ids=("doc-1:p4:b4",),
                    ),
                ],
            )
        ],
    )


def test_block_neighbor_policy_expands_each_block_with_same_section_neighbors() -> None:
    nodes = parsed_document_to_chunked_nodes(_chunk_policy_doc(), policy_name="block_neighbor_1")

    equation_node = next(node for node in nodes if node.metadata["block_id"] == "doc-1:p4:b2")

    assert "dimensions must align" in equation_node.text
    assert "$C = AB$ has shape" in equation_node.text
    assert "summing over k" in equation_node.text
    assert "identity matrix" not in equation_node.text
    assert equation_node.metadata["chunk_policy"] == "block_neighbor_1"
    assert equation_node.metadata["source_block_ids"] == [
        "doc-1:p4:b1",
        "doc-1:p4:b2",
        "doc-1:p4:b3",
    ]
    assert equation_node.metadata["source_block_types"] == ["paragraph", "equation", "paragraph"]


def test_page_section_window_policy_merges_adjacent_blocks_within_section() -> None:
    nodes = parsed_document_to_chunked_nodes(
        _chunk_policy_doc(), policy_name="page_section_window_512"
    )

    first_window = nodes[0]

    assert "Multiplying Matrices and Vectors" in first_window.text
    assert "dimensions must align" in first_window.text
    assert "$C = AB$ has shape" in first_window.text
    assert "identity matrix" not in first_window.text
    assert first_window.metadata["chunk_policy"] == "page_section_window_512"
    assert first_window.metadata["source_block_ids"] == [
        "doc-1:p4:b0",
        "doc-1:p4:b1",
        "doc-1:p4:b2",
        "doc-1:p4:b3",
    ]


def test_math_object_window_policy_centers_equation_chunks_on_surrounding_prose() -> None:
    nodes = parsed_document_to_chunked_nodes(_chunk_policy_doc(), policy_name="math_object_window")

    equation_window = next(
        node for node in nodes if node.metadata["chunk_kind"] == "equation_window"
    )

    assert "dimensions must align" in equation_window.text
    assert "$C = AB$ has shape" in equation_window.text
    assert "summing over k" in equation_window.text
    assert equation_window.metadata["block_id"] == "doc-1:p4:b2"
    assert equation_window.metadata["chunk_policy"] == "math_object_window"
    assert equation_window.metadata["source_block_ids"] == [
        "doc-1:p4:b1",
        "doc-1:p4:b2",
        "doc-1:p4:b3",
    ]
