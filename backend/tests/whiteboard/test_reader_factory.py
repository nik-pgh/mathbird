import pytest

from app.agent.whiteboard.reader import BoardReader, get_board_reader
from app.agent.whiteboard.reader.null import NullBoardReader
from app.config import get_settings


@pytest.fixture(autouse=True)
def _reset_caches():
    get_settings.cache_clear()
    get_board_reader.cache_clear()
    yield
    get_settings.cache_clear()
    get_board_reader.cache_clear()


def test_factory_defaults_to_null(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOARD_READER", "null")
    reader = get_board_reader()

    assert isinstance(reader, NullBoardReader)
    assert isinstance(reader, BoardReader)


def test_factory_returns_openai_vision_when_selected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BOARD_READER", "openai_vision")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    reader = get_board_reader()

    # We assert by class name to avoid importing the module at the top of the
    # test file (which would defeat the lazy-import contract of the factory).
    assert type(reader).__name__ == "OpenAIVisionBoardReader"


def test_factory_unknown_provider_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOARD_READER", "made_up")
    with pytest.raises(Exception):  # noqa: B017
        # Settings rejects unknown literals; get_board_reader may also raise.
        # Either error is acceptable — we just want a hard failure.
        get_board_reader()
