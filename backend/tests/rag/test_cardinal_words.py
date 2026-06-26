import pytest

from app.rag.cardinal_words import parse_cardinal_words


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("7", 7),
        ("forty", 40),
        ("forty two", 42),
        ("forty-two", 42),
        ("one hundred twenty three", 123),
        ("ninety six", 96),
        ("twenty", 20),
        ("zero", 0),
    ],
)
def test_parse_cardinal_words(text: str, expected: int) -> None:
    assert parse_cardinal_words(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "approach",
        "forty bananas",
    ],
)
def test_parse_cardinal_words_rejects_invalid(text: str) -> None:
    assert parse_cardinal_words(text) is None
