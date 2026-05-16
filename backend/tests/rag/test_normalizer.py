import pytest

from app.rag.parsing import (
    ParsedBlock,
    ParsedDocument,
    ParsedPage,
    RetrievalRequest,
    RetrievedContext,
    RetrievedRecord,
)


def test_parsed_block_source_label_includes_problem_number() -> None:
    doc = ParsedDocument(
        doc_id="doc-1",
        filename="Spectrum Math 6.pdf",
        pages=[
            ParsedPage(
                page_number=37,
                text="Problem 8. Solve 2x + 3 = 9.",
                blocks=[
                    ParsedBlock(
                        block_id="doc-1:p37:b0",
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

    assert doc.page_count == 1
    assert doc.pages[0].blocks[0].source_label("Spectrum Math 6.pdf") == (
        "Spectrum Math 6.pdf, page 37, problem 8"
    )


def test_parsed_models_coerce_collections_to_tuples() -> None:
    block = ParsedBlock(
        block_id="doc-1:p37:b0",
        page_number=37,
        block_type="exercise",
        text="Problem 8. Solve 2x + 3 = 9.",
        image_refs=["graph-1.png"],
        neighboring_block_ids=["doc-1:p37:b1"],
    )
    page = ParsedPage(page_number=37, text=block.text, blocks=[block])
    doc = ParsedDocument(doc_id="doc-1", filename="Spectrum Math 6.pdf", pages=[page])
    request = RetrievalRequest(
        query="solve",
        doc_ids=["doc-1"],
        requested_modalities=["text", "image"],
    )
    record = RetrievedRecord(
        text=block.text,
        filename=doc.filename,
        page_number=37,
        visual_refs=["graph-1.png"],
    )
    context = RetrievedContext(
        records=[record],
        citations=["Spectrum Math 6.pdf, page 37"],
        visual_refs=["graph-1.png"],
    )

    assert block.image_refs == ("graph-1.png",)
    assert block.neighboring_block_ids == ("doc-1:p37:b1",)
    assert page.blocks == (block,)
    assert doc.pages == (page,)
    assert request.doc_ids == ("doc-1",)
    assert request.requested_modalities == ("text", "image")
    assert record.visual_refs == ("graph-1.png",)
    assert context.records == (record,)
    assert context.citations == ("Spectrum Math 6.pdf, page 37",)
    assert context.visual_refs == ("graph-1.png",)


def test_retrieval_request_student_context_is_copied_read_only_mapping() -> None:
    student_context = {"grade": 6}
    request = RetrievalRequest(query="solve", student_context=student_context)

    student_context["grade"] = 7

    assert request.student_context["grade"] == 6
    with pytest.raises(TypeError):
        request.student_context["grade"] = 8


def test_content_for_embedding_uses_text_for_blank_markdown_and_includes_modalities() -> None:
    block = ParsedBlock(
        block_id="doc-1:p37:b1",
        page_number=37,
        block_type="equation",
        text="Solve 2x + 3 = 9.",
        markdown="   ",
        latex="2x + 3 = 9",
        image_refs=("graph-1.png", "diagram-2.png"),
    )

    assert block.content_for_embedding() == (
        "Solve 2x + 3 = 9.\n"
        "Equation: 2x + 3 = 9\n"
        "Visual references: graph-1.png, diagram-2.png"
    )
