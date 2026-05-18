import pytest

from app.agent.whiteboard.reader import BoardReader, get_board_reader
from app.agent.whiteboard.reader.null import NullBoardReader
from app.agent.whiteboard.reader.openai_vision import OpenAIVisionBoardReader
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


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content: str) -> None:
        self._content = content
        self.last_kwargs: dict | None = None

    async def create(self, **kwargs: object):
        self.last_kwargs = kwargs
        return _FakeCompletion(self._content)


class _FakeChat:
    def __init__(self, completions: _FakeCompletions) -> None:
        self.completions = completions


class _FakeClient:
    def __init__(self, content: str) -> None:
        self.chat = _FakeChat(_FakeCompletions(content))


async def test_openai_vision_reader_sends_image_and_returns_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _FakeClient("2x + 3 = 9")
    reader = OpenAIVisionBoardReader(model="gpt-4o-mini", api_key="sk-test")
    monkeypatch.setattr(reader, "_client", fake_client)

    out = await reader.interpret(b"\x89PNG\r\n\x1a\nfake")

    assert out == "2x + 3 = 9"
    assert fake_client.chat.completions.last_kwargs is not None
    assert fake_client.chat.completions.last_kwargs["model"] == "gpt-4o-mini"
    # The image must be sent as a base64 data URL inside the user message.
    msgs = fake_client.chat.completions.last_kwargs["messages"]
    user_msg = next(m for m in msgs if m["role"] == "user")
    parts = user_msg["content"]
    image_part = next(p for p in parts if p["type"] == "image_url")
    assert image_part["image_url"]["url"].startswith("data:image/png;base64,")


async def test_openai_vision_reader_returns_empty_string_on_client_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _ExplodingCompletions:
        async def create(self, **kwargs: object):  # noqa: ARG002
            raise RuntimeError("boom")

    class _ExplodingClient:
        def __init__(self) -> None:
            self.chat = _FakeChat(_ExplodingCompletions())  # type: ignore[arg-type]

    reader = OpenAIVisionBoardReader(model="gpt-4o-mini", api_key="sk-test")
    monkeypatch.setattr(reader, "_client", _ExplodingClient())

    out = await reader.interpret(b"\x89PNG")

    assert out == ""
