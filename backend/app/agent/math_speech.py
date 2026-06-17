"""Normalize math-heavy text before it is sent to text-to-speech.

The LLM and AiBoard extractor should still see symbolic math. This module is
only for the spoken TTS stream, where providers often read raw LaTeX or symbols
literally.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterable, AsyncIterator

from app.agent.whiteboard.sentence import split_sentences

_LATEX_COMMANDS = {
    r"\times": " times ",
    r"\cdot": " times ",
    r"\div": " divided by ",
    r"\pm": " plus or minus ",
    r"\leq": " is less than or equal to ",
    r"\le": " is less than or equal to ",
    r"\geq": " is greater than or equal to ",
    r"\ge": " is greater than or equal to ",
    r"\neq": " is not equal to ",
    r"\ne": " is not equal to ",
    r"\approx": " is approximately ",
    r"\to": " approaches ",
    r"\rightarrow": " approaches ",
    r"\infty": " infinity ",
    r"\pi": " pi ",
    r"\theta": " theta ",
    r"\alpha": " alpha ",
    r"\beta": " beta ",
    r"\gamma": " gamma ",
    r"\delta": " delta ",
    r"\lambda": " lambda ",
    r"\mu": " mu ",
    r"\sigma": " sigma ",
    r"\sin": " sine ",
    r"\cos": " cosine ",
    r"\tan": " tangent ",
    r"\log": " log ",
    r"\ln": " natural log ",
}

_SYMBOLS = {
    "≤": " is less than or equal to ",
    "≥": " is greater than or equal to ",
    "≠": " is not equal to ",
    "≈": " is approximately ",
    "∞": " infinity ",
    "π": " pi ",
    "θ": " theta ",
    "α": " alpha ",
    "β": " beta ",
    "γ": " gamma ",
    "δ": " delta ",
    "λ": " lambda ",
    "μ": " mu ",
    "σ": " sigma ",
    "×": " times ",
    "·": " times ",
    "÷": " divided by ",
}

_WRAPPER_REPLACEMENTS = (
    ("$$", ""),
    ("$", ""),
    (r"\(", ""),
    (r"\)", ""),
    (r"\[", ""),
    (r"\]", ""),
)


def _replace_simple_latex_commands(text: str) -> str:
    commands = sorted(_LATEX_COMMANDS.items(), key=lambda item: len(item[0]), reverse=True)
    for command, spoken in commands:
        text = text.replace(command, spoken)
    return text


def _replace_braced_commands(text: str) -> str:
    previous = None
    while previous != text:
        previous = text
        text = re.sub(
            r"\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}",
            lambda match: (
                f"{math_to_speech_text(match.group(1))} over "
                f"{math_to_speech_text(match.group(2))}"
            ),
            text,
        )
        text = re.sub(
            r"\\sqrt\s*\{([^{}]*)\}",
            lambda match: f"square root of {math_to_speech_text(match.group(1))}",
            text,
        )
    return text


def _replace_exponents(text: str) -> str:
    def replacement(match: re.Match[str]) -> str:
        base = match.group("base")
        exponent = match.group("braced") or match.group("plain") or ""
        spoken_exponent = math_to_speech_text(exponent)
        if exponent == "2":
            return f"{base} squared"
        if exponent == "3":
            return f"{base} cubed"
        return f"{base} to the power of {spoken_exponent}"

    return re.sub(
        r"(?P<base>[A-Za-z0-9]+)\s*\^\s*(?:\{(?P<braced>[^{}]+)\}|(?P<plain>[A-Za-z0-9]+))",
        replacement,
        text,
    )


def _replace_operators(text: str) -> str:
    for symbol, spoken in _SYMBOLS.items():
        text = text.replace(symbol, spoken)

    text = re.sub(r">=", " is greater than or equal to ", text)
    text = re.sub(r"<=", " is less than or equal to ", text)
    text = re.sub(r"!=", " is not equal to ", text)
    text = re.sub(r"(?<![\w.])-+\s*(\d+(?:\.\d+)?)", r" negative \1", text)
    text = text.replace("=", " equals ")
    text = text.replace("+", " plus ")
    text = re.sub(r"\s-\s", " minus ", text)
    text = text.replace("*", " times ")
    text = text.replace("/", " over ")
    text = text.replace(">", " is greater than ")
    return text.replace("<", " is less than ")


def _cleanup(text: str) -> str:
    text = re.sub(r"(?<=\d)(?=[A-Za-z])", " ", text)
    text = re.sub(r"(?<=[A-Za-z])_(\d+|[A-Za-z])", r" sub \1", text)
    text = re.sub(r"\s+([,.?!;:])", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def math_to_speech_text(text: str) -> str:
    """Convert common math notation into words that TTS reads naturally."""
    for old, new in _WRAPPER_REPLACEMENTS:
        text = text.replace(old, new)
    text = _replace_braced_commands(text)
    text = _replace_simple_latex_commands(text)
    text = _replace_exponents(text)
    text = _replace_operators(text)
    return _cleanup(text)


async def spoken_math_stream(text: AsyncIterable[str]) -> AsyncIterator[str]:
    """Yield sentence-sized TTS chunks with math notation verbalized."""
    buffer = ""
    async for chunk in text:
        buffer += chunk
        sentences, buffer = split_sentences(buffer)
        for sentence in sentences:
            yield f"{math_to_speech_text(sentence)} "

    tail = buffer.strip()
    if tail:
        yield math_to_speech_text(tail)
