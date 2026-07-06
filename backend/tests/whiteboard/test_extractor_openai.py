"""``OpenAIBoardExtractor`` uses ``client.beta.chat.completions.parse`` with
a pydantic response_format for structured outputs.

We inject a fake client at construction so unit tests are fast and
deterministic. A separate ``@pytest.mark.integration`` test (skipped by
default) exercises the real API.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import ValidationError

from app.agent.whiteboard.extractor.openai import (
    ExtractorResponse,
    OpenAIBoardExtractor,
)
from app.agent.whiteboard.messages import AiBoardDiagram, AiBoardPlot, AiBoardText


@dataclass
class _FakeParsedChoice:
    message: Any


@dataclass
class _FakeMessage:
    parsed: ExtractorResponse | None


@dataclass
class _FakeCompletion:
    choices: list[_FakeParsedChoice]


class _FakeCompletions:
    def __init__(self, response: ExtractorResponse | Exception):
        self._response = response
        self.calls: list[dict] = []

    async def parse(self, **kwargs: Any) -> _FakeCompletion:
        self.calls.append(kwargs)
        if isinstance(self._response, Exception):
            raise self._response
        return _FakeCompletion(
            choices=[_FakeParsedChoice(message=_FakeMessage(parsed=self._response))]
        )


class _FakeChat:
    def __init__(self, response):
        self.completions = _FakeCompletions(response)


class _FakeBeta:
    def __init__(self, response):
        self.chat = _FakeChat(response)


class _FakeClient:
    def __init__(self, response):
        self.beta = _FakeBeta(response)


def _make_extractor(response) -> OpenAIBoardExtractor:
    return OpenAIBoardExtractor(
        model="gpt-4o-mini",
        timeout=2.0,
        client=_FakeClient(response),
    )


async def test_extract_returns_parsed_items() -> None:
    expected = ExtractorResponse(
        items=[AiBoardText(kind="text", id="eq1", markdown="$2x + 5 = 10$")]
    )
    ex = _make_extractor(expected)

    items = await ex.extract(
        sentence="Let's set up 2x + 5 = 10.",
        current_items=[],
        last_sentence=None,
    )

    assert len(items) == 1
    assert items[0].id == "eq1"
    assert isinstance(items[0], AiBoardText)


async def test_extract_passes_sentence_and_current_items_to_prompt() -> None:
    ex = _make_extractor(ExtractorResponse(items=[]))

    existing = AiBoardText(kind="text", id="eq1", markdown="$2x + 5 = 10$")
    await ex.extract(
        sentence="Now we subtract 5.",
        current_items=[existing],
        last_sentence="Let's set up 2x + 5 = 10.",
    )

    # The fake records the kwargs passed to parse(). Verify the user
    # message contains the sentence, the prior sentence, and the current
    # items JSON.
    call = ex._client.beta.chat.completions.calls[0]
    messages = call["messages"]
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    user_content = messages[1]["content"]
    assert "Now we subtract 5." in user_content
    assert "Let's set up 2x + 5 = 10." in user_content
    assert "eq1" in user_content  # current items JSON includes the existing id


async def test_extract_returns_empty_list_when_response_has_no_items() -> None:
    ex = _make_extractor(ExtractorResponse(items=[]))

    items = await ex.extract(
        sentence="What do you think happens next?",
        current_items=[],
        last_sentence=None,
    )

    assert items == []


async def test_extract_returns_empty_on_api_error() -> None:
    # Treat API errors as "skip this sentence and continue"; do NOT raise.
    ex = _make_extractor(RuntimeError("upstream 500"))

    items = await ex.extract(
        sentence="Let's set up 2x + 5 = 10.",
        current_items=[],
        last_sentence=None,
    )

    assert items == []


async def test_extract_returns_empty_on_timeout() -> None:
    class _SlowCompletions:
        async def parse(self, **kwargs: Any) -> Any:
            await asyncio.sleep(5.0)
            raise AssertionError("should not reach")

    class _SlowChat:
        completions = _SlowCompletions()

    class _SlowBeta:
        chat = _SlowChat()

    class _SlowClient:
        beta = _SlowBeta()

    ex = OpenAIBoardExtractor(
        model="gpt-4o-mini",
        timeout=0.05,  # 50ms — guaranteed to expire
        client=_SlowClient(),
    )

    items = await ex.extract(
        sentence="anything",
        current_items=[],
        last_sentence=None,
    )

    assert items == []


async def test_extract_plot_kind() -> None:
    expected = ExtractorResponse(items=[AiBoardPlot(kind="plot", id="p1", expression="x**2")])
    ex = _make_extractor(expected)

    items = await ex.extract(
        sentence="The function y = x squared is a parabola.",
        current_items=[],
        last_sentence=None,
    )

    assert isinstance(items[0], AiBoardPlot)
    assert items[0].expression == "x**2"


async def test_extract_diagram_kind() -> None:
    expected = ExtractorResponse(
        items=[
            AiBoardDiagram(
                kind="diagram",
                id="d1",
                syntax="mermaid",
                source="flowchart TD\n  A[42] --> B[2]\n  A --> C[21]",
                label="Factor tree",
            )
        ]
    )
    ex = _make_extractor(expected)

    items = await ex.extract(
        sentence="Draw a factor tree for 42.",
        current_items=[],
        last_sentence=None,
    )

    assert isinstance(items[0], AiBoardDiagram)
    assert items[0].syntax == "mermaid"


async def test_extractor_prompt_contains_mermaid_and_shape_rules() -> None:
    ex = _make_extractor(ExtractorResponse(items=[]))

    await ex.extract(
        sentence="Draw a factor tree for 42.",
        current_items=[],
        last_sentence=None,
    )

    system = ex._client.beta.chat.completions.calls[0]["messages"][0]["content"]
    assert "Mermaid" in system
    assert "flowchart TD" in system
    assert "number line" in system
    assert "shape" in system
    assert "proactive" in system.lower()


def test_extractor_response_schema_uses_AiBoardItem_discriminator() -> None:
    # ExtractorResponse should accept any AiBoardItem kind (text/plot/shape)
    # and reject items with unknown kinds.
    valid = ExtractorResponse.model_validate(
        {"items": [{"kind": "text", "id": "eq1", "markdown": "$x = 1$"}]}
    )
    assert len(valid.items) == 1

    with pytest.raises(ValidationError):
        ExtractorResponse.model_validate({"items": [{"kind": "bogus", "id": "x", "data": "x"}]})


def test_extractor_response_schema_uses_anyOf_not_oneOf() -> None:
    # Regression: OpenAI Structured Outputs rejects oneOf. Pydantic emits
    # oneOf for the discriminated AiBoardItem union (because of
    # Field(discriminator="kind") in messages.py) but anyOf for a plain
    # union. The ExtractorResponse schema must use anyOf so it passes
    # OpenAI's validation.
    schema = ExtractorResponse.model_json_schema()
    schema_str = str(schema)
    assert "oneOf" not in schema_str, (
        "ExtractorResponse schema must not contain 'oneOf' — OpenAI rejects it. "
        f"Full schema: {schema}"
    )
    # And it should still describe an items array with multiple variants:
    items_field = schema["properties"]["items"]
    inner = items_field["items"]
    # Either anyOf at the top level, or a $ref that ultimately resolves to anyOf.
    assert "anyOf" in str(inner) or "$ref" in inner or "anyOf" in str(schema), (
        f"items field schema looks wrong: {inner}"
    )
