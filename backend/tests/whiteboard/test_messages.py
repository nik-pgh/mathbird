import pytest
from pydantic import ValidationError

from app.agent.whiteboard.messages import (
    AI_BOARD_TOPIC,
    USER_BOARD_TOPIC,
    AiBoardPlot,
    AiBoardShape,
    AiBoardText,
    AiBoardUpdate,
    UserBoardSnapshot,
)


def test_topic_constants_are_stable() -> None:
    assert AI_BOARD_TOPIC == "ai_board"
    assert USER_BOARD_TOPIC == "user_board"


def test_ai_board_update_round_trips_mixed_items() -> None:
    update = AiBoardUpdate(
        op="upsert",
        items=[
            AiBoardText(kind="text", id="t1", markdown="Solve $2x + 3 = 9$."),
            AiBoardPlot(kind="plot", id="p1", expression="x**2 - 4", x_min=-3, x_max=3),
            AiBoardShape(kind="shape", id="s1", svg='<circle cx="10" cy="10" r="5"/>'),
        ],
    )

    dumped = update.model_dump_json()
    restored = AiBoardUpdate.model_validate_json(dumped)

    assert len(restored.items) == 3
    assert restored.items[0].kind == "text"
    assert restored.items[1].kind == "plot"
    assert restored.items[2].kind == "shape"


def test_ai_board_item_requires_kind_field_in_json() -> None:
    # Regression: an LLM tool-call payload that omits ``kind`` from items
    # must fail validation with a clear discriminator error rather than
    # silently falling through to one of the variants. The corresponding
    # JSON Schema marks ``kind`` as required (no default) so OpenAI sends
    # the LLM a schema that demands the field on every item.
    with pytest.raises(ValidationError) as exc_info:
        AiBoardUpdate.model_validate(
            {"op": "upsert", "items": [{"id": "x", "markdown": "hi"}]}
        )
    assert "kind" in str(exc_info.value)


def test_ai_board_text_schema_marks_kind_required() -> None:
    schema = AiBoardText.model_json_schema()
    assert "kind" in schema["required"]
    # No top-level ``default`` on the property either — that's what made
    # OpenAI treat ``kind`` as optional in the function-tool schema.
    assert "default" not in schema["properties"]["kind"]


def test_ai_board_update_clear_takes_no_items() -> None:
    update = AiBoardUpdate(op="clear")

    assert update.items == []


def test_ai_board_item_unknown_kind_rejected() -> None:
    with pytest.raises(ValidationError):
        AiBoardUpdate.model_validate(
            {"op": "upsert", "items": [{"kind": "nope", "id": "x"}]}
        )


def test_user_board_snapshot_round_trips() -> None:
    snap = UserBoardSnapshot(
        png_b64="aGVsbG8=",  # "hello"
        captured_at_ms=1700000000123,
        is_empty=False,
    )
    restored = UserBoardSnapshot.model_validate_json(snap.model_dump_json())

    assert restored.png_b64 == "aGVsbG8="
    assert restored.captured_at_ms == 1700000000123
    assert restored.is_empty is False
