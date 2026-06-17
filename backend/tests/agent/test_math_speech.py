"""Math text normalization used before sending text to TTS."""

from __future__ import annotations

from app.agent.math_speech import math_to_speech_text, spoken_math_stream


async def _collect(chunks: list[str]) -> list[str]:
    async def source():
        for chunk in chunks:
            yield chunk

    return [chunk async for chunk in spoken_math_stream(source())]


def test_math_to_speech_text_expands_inline_equation_symbols() -> None:
    assert math_to_speech_text("Let's solve $2x + 5 = 10$.") == (
        "Let's solve 2 x plus 5 equals 10."
    )


def test_math_to_speech_text_expands_latex_fraction_and_exponent() -> None:
    assert math_to_speech_text(r"$x^2 = \frac{1}{4}$") == "x squared equals 1 over 4"


def test_math_to_speech_text_expands_common_math_unicode_symbols() -> None:
    assert math_to_speech_text("If x ≥ 0, then y ≠ -1.") == (
        "If x is greater than or equal to 0, then y is not equal to negative 1."
    )


async def test_spoken_math_stream_normalizes_equations_split_across_chunks() -> None:
    chunks = await _collect(["Now $x", "^2 + 1 = 5$. ", "What is x? "])

    assert chunks == ["Now x squared plus 1 equals 5. ", "What is x? "]


async def test_spoken_math_stream_flushes_trailing_partial_text() -> None:
    chunks = await _collect(["Try $\\sqrt{x}", " = 3$"])

    assert chunks == ["Try square root of x equals 3"]
