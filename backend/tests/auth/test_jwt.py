from __future__ import annotations

import pytest

from app.auth.jwt import decode_token, decode_session, issue_token
from app.config import get_settings


@pytest.fixture(autouse=True)
def auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_JWT_SECRET", "test-secret-key-at-least-32-chars!!")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_issue_and_decode_round_trip() -> None:
    token = issue_token(
        "user-abc",
        email="alice@example.com",
        name="Alice",
        google_sub="google-sub-1",
    )
    claims = decode_session(token)
    assert claims.user_id == "user-abc"
    assert claims.email == "alice@example.com"
    assert decode_token(token) == "user-abc"
