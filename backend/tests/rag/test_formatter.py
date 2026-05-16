from app.rag.formatter import format_records_as_chunks
from app.rag.parsing import RetrievedRecord


def test_format_records_as_cited_chunks() -> None:
    records = [
        RetrievedRecord(
            text="Solve 2x + 3 = 9.",
            filename="Spectrum Math 6.pdf",
            page_number=37,
            exercise_number="8",
            score=0.91,
        )
    ]

    chunks = format_records_as_chunks(records)

    assert len(chunks) == 1
    assert chunks[0].source == "Spectrum Math 6.pdf, page 37, problem 8"
    assert chunks[0].text == "Solve 2x + 3 = 9."
    assert chunks[0].score == 0.91


def test_format_records_deduplicates_by_block_id() -> None:
    records = [
        RetrievedRecord(
            text="same",
            filename="book.pdf",
            page_number=1,
            block_id="b1",
        ),
        RetrievedRecord(
            text="same again",
            filename="book.pdf",
            page_number=1,
            block_id="b1",
        ),
    ]

    chunks = format_records_as_chunks(records)

    assert len(chunks) == 1
    assert chunks[0].text == "same"
