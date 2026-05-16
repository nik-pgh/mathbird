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


def test_format_records_skips_whitespace_only_text() -> None:
    records = [
        RetrievedRecord(
            text="  \n\t  ",
            filename="book.pdf",
            page_number=1,
        )
    ]

    chunks = format_records_as_chunks(records)

    assert chunks == []


def test_format_records_blank_duplicate_does_not_hide_nonblank_block() -> None:
    records = [
        RetrievedRecord(
            text="   ",
            filename="book.pdf",
            page_number=1,
            block_id="b1",
        ),
        RetrievedRecord(
            text="kept",
            filename="book.pdf",
            page_number=1,
            block_id="b1",
        ),
    ]

    chunks = format_records_as_chunks(records)

    assert len(chunks) == 1
    assert chunks[0].text == "kept"


def test_format_records_deduplicates_fallback_by_source_and_stripped_text() -> None:
    records = [
        RetrievedRecord(
            text="same",
            filename="book.pdf",
            page_number=1,
        ),
        RetrievedRecord(
            text=" same ",
            filename="book.pdf",
            page_number=1,
        ),
    ]

    chunks = format_records_as_chunks(records)

    assert len(chunks) == 1
    assert chunks[0].text == "same"
