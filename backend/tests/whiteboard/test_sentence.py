"""``split_sentences`` is a pure function that pulls complete sentences off
the front of a buffer string and returns them + the remainder.
"""

from __future__ import annotations

from app.agent.whiteboard.sentence import split_sentences


def test_no_terminator_returns_no_sentences() -> None:
    sentences, remainder = split_sentences("hello world")
    assert sentences == []
    assert remainder == "hello world"


def test_single_sentence_with_period() -> None:
    sentences, remainder = split_sentences("Hello world. ")
    assert sentences == ["Hello world."]
    assert remainder == ""


def test_question_mark_boundary() -> None:
    sentences, remainder = split_sentences("What is x? Now solve. ")
    assert sentences == ["What is x?", "Now solve."]
    assert remainder == ""


def test_exclamation_boundary() -> None:
    sentences, remainder = split_sentences("Great work! Next step. ")
    assert sentences == ["Great work!", "Next step."]
    assert remainder == ""


def test_newline_always_flushes() -> None:
    sentences, remainder = split_sentences("Line one\nLine two")
    assert sentences == ["Line one"]
    assert remainder == "Line two"


def test_abbreviation_does_not_split() -> None:
    # "Dr." is followed by lowercase "s" — not a sentence boundary.
    sentences, remainder = split_sentences("Dr. smith is here. ")
    assert sentences == ["Dr. smith is here."]
    assert remainder == ""


def test_decimal_does_not_split() -> None:
    # "0.5" — the period is followed by a digit, not uppercase.
    sentences, remainder = split_sentences("The answer is 0.5 exactly. ")
    assert sentences == ["The answer is 0.5 exactly."]
    assert remainder == ""


def test_trailing_partial_sentence_kept_as_remainder() -> None:
    sentences, remainder = split_sentences("Done. Now partial")
    assert sentences == ["Done."]
    assert remainder == "Now partial"


def test_max_buffer_safety_valve_flushes() -> None:
    # 200-char safety valve: if no terminator and buffer >= 200 chars,
    # flush whatever we have so we don't buffer indefinitely.
    text = "a" * 250
    sentences, remainder = split_sentences(text)
    assert len(sentences) == 1
    assert sentences[0] == text
    assert remainder == ""


def test_empty_input() -> None:
    sentences, remainder = split_sentences("")
    assert sentences == []
    assert remainder == ""


def test_only_whitespace() -> None:
    sentences, remainder = split_sentences("   ")
    assert sentences == []
    assert remainder == "   "
