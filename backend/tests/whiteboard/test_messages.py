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
            AiBoardText(id="t1", markdown="Solve $2x + 3 = 9$."),
            AiBoardPlot(id="p1", expression="x**2 - 4", x_min=-3, x_max=3),
            AiBoardShape(id="s1", svg='<circle cx="10" cy="10" r="5"/>'),
        ],
    )

    dumped = update.model_dump_json()
    restored = AiBoardUpdate.model_validate_json(dumped)

    assert len(restored.items) == 3
    assert restored.items[0].kind == "text"
    assert restored.items[1].kind == "plot"
    assert restored.items[2].kind == "shape"


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
