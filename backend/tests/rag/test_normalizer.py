import pytest

from app.rag.normalizer import normalize_llamaparse_items
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
    bbox = [0.1, 0.2, 0.3, 0.4]
    block = ParsedBlock(
        block_id="doc-1:p37:b0",
        page_number=37,
        block_type="exercise",
        text="Problem 8. Solve 2x + 3 = 9.",
        image_refs=["graph-1.png"],
        bbox=bbox,
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
    bbox[0] = 9.9

    assert block.image_refs == ("graph-1.png",)
    assert block.bbox == (0.1, 0.2, 0.3, 0.4)
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
    student_context = {
        "grade": 6,
        "progress": {
            "completed": ["lesson-1"],
            "scores": [{"lesson": "lesson-1", "score": 90}],
        },
        "standards": {"6.EE.A.2"},
    }
    request = RetrievalRequest(query="solve", student_context=student_context)

    student_context["grade"] = 7
    student_context["progress"]["completed"].append("lesson-2")
    student_context["progress"]["scores"][0]["score"] = 50
    student_context["standards"].add("6.EE.B.5")

    assert request.student_context["grade"] == 6
    assert request.student_context["progress"]["completed"] == ("lesson-1",)
    assert request.student_context["progress"]["scores"][0]["score"] == 90
    assert request.student_context["standards"] == frozenset({"6.EE.A.2"})
    with pytest.raises(TypeError):
        request.student_context["grade"] = 8
    with pytest.raises(TypeError):
        request.student_context["progress"]["scores"][0]["score"] = 75


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


def test_normalize_llamaparse_items_detects_heading_exercise_and_neighbors() -> None:
    payload = {
        "items": {
            "pages": [
                {
                    "page": 37,
                    "items": [
                        {
                            "type": "heading",
                            "value": "Solving Equations",
                            "md": "# Solving Equations",
                        },
                        {
                            "type": "text",
                            "value": "Example 2. Solve x + 4 = 10.",
                            "md": "Example 2. Solve x + 4 = 10.",
                        },
                        {
                            "type": "text",
                            "value": "Problem 8. Solve 2x + 3 = 9.",
                            "md": "Problem 8. Solve 2x + 3 = 9.",
                        },
                    ],
                }
            ]
        }
    }

    doc = normalize_llamaparse_items(payload, doc_id="doc-1", filename="Spectrum Math 6.pdf")

    assert doc.pages[0].page_number == 37
    assert doc.pages[0].blocks[0].block_type == "heading"
    assert doc.pages[0].blocks[1].block_type == "example"
    assert doc.pages[0].blocks[2].block_type == "exercise"
    assert doc.pages[0].blocks[2].exercise_number == "8"
    assert doc.pages[0].blocks[2].section_title == "Solving Equations"
    assert doc.pages[0].blocks[2].neighboring_block_ids == ("doc-1:p37:b1",)


def test_normalize_llamaparse_items_preserves_image_refs() -> None:
    payload = {
        "items": {
            "pages": [
                {
                    "page": 5,
                    "items": [
                        {
                            "type": "image",
                            "value": "Coordinate graph showing a line.",
                            "md": "![graph](image_0.png)",
                            "image_filename": "image_0.png",
                        }
                    ],
                }
            ]
        },
        "images_content_metadata": {
            "images": [
                {
                    "filename": "image_0.png",
                    "category": "layout",
                    "presigned_url": "https://example.com/image_0.png",
                }
            ]
        },
    }

    doc = normalize_llamaparse_items(payload, doc_id="doc-1", filename="book.pdf")

    assert doc.pages[0].blocks[0].block_type == "image"
    assert doc.pages[0].blocks[0].image_refs == ("doc-1:image_0.png",)
