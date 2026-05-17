"""Tests for /api/token route — active_doc_id metadata round-trip."""

from __future__ import annotations

import base64
import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.config import get_settings


@pytest.fixture(autouse=True)
def livekit_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("LIVEKIT_URL", "wss://example.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "test-key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "x" * 32)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _decode_jwt_payload(token: str) -> dict:
    parts = token.split(".")
    payload = parts[1]
    # JWT base64url is unpadded.
    padding = "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload + padding))


def test_token_request_includes_active_doc_id_in_metadata() -> None:
    client = TestClient(app)
    res = client.post("/api/token", json={"doc_id": "abc123"})
    assert res.status_code == 200

    payload = _decode_jwt_payload(res.json()["token"])
    metadata = json.loads(payload["metadata"])
    assert metadata == {"active_doc_id": "abc123"}


def test_token_request_without_doc_id_omits_metadata_field() -> None:
    client = TestClient(app)
    res = client.post("/api/token", json={})
    assert res.status_code == 200

    payload = _decode_jwt_payload(res.json()["token"])
    # When no doc_id is supplied, the metadata claim is either absent or "".
    metadata_raw = payload.get("metadata", "")
    assert metadata_raw in ("", None)
