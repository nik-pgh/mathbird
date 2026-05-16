from app.agent.whiteboard.reader.null import NullBoardReader


async def test_null_reader_returns_empty_string() -> None:
    reader = NullBoardReader()
    result = await reader.interpret(b"\x89PNG\r\n\x1a\n...not really a png...")

    assert result == ""
