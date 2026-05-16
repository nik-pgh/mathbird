from app.config import Settings


def test_board_reader_defaults_to_null(monkeypatch) -> None:
    monkeypatch.delenv("BOARD_READER", raising=False)
    monkeypatch.delenv("BOARD_READER_MODEL", raising=False)
    monkeypatch.delenv("BOARD_READER_INTERVAL_SECONDS", raising=False)
    monkeypatch.delenv("BOARD_READER_MAX_IMAGE_DIM", raising=False)

    settings = Settings()

    assert settings.board_reader == "null"
    assert settings.board_reader_model == "gpt-4o-mini"
    assert settings.board_reader_interval_seconds == 2.0
    assert settings.board_reader_max_image_dim == 512


def test_board_reader_accepts_openai_vision() -> None:
    settings = Settings(board_reader="openai_vision")

    assert settings.board_reader == "openai_vision"
