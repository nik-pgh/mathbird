import pytest

from app.rag.chapter import parse_chapter_number


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("chapter 2 linear algebra", 2),
        ("Chapter2 Linear Algebra", 2),
        ("CHAPTER2.LINEARALGEBRA", 2),
        ("read ch. 5 on backprop", 5),
        ("no chapter here", None),
    ],
)
def test_parse_chapter_number(text: str, expected: int | None) -> None:
    assert parse_chapter_number(text) == expected
