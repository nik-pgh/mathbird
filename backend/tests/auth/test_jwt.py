from __future__ import annotations

import pytest

from app.auth.jwt import decode_token, issue_token
from app.config import get_settings


@pytest.fixture(autouse=True)
def auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_JWT_SECRET", "test-secret-key-at-least-32-chars!!")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_issue_and_decode_round_trip() -> None:
    token = issue_token("user-abc")
    assert decode_token(token) == "user-abc"
