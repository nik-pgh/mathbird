from app.rag.parsing import ParsedBlock, ParsedDocument, ParsedPage


def test_parsed_document_collects_page_text() -> None:
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
