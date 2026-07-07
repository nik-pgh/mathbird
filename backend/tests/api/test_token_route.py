"""Tests for /api/token route — auth, user_id, and active_doc_id metadata."""

from __future__ import annotations

import base64
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.config import get_settings
from tests.api.conftest import make_auth_client, upload_pdf


@pytest.fixture(autouse=True)
def livekit_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("LIVEKIT_URL", "wss://example.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "test-key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "x" * 32)
    monkeypatch.setenv("GUEST_SAMPLE_DOC_ID", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _decode_jwt_payload(token: str) -> dict:
    parts = token.split(".")
    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload + padding))


def test_token_without_guest_config_rejects_anonymous() -> None:
    """When GUEST_SAMPLE_DOC_ID is not set, anonymous requests get 401."""
    client = TestClient(app)
    res = client.post("/api/token", json={})
    assert res.status_code == 401


def test_guest_token_uses_sample_doc(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guest session gets an ephemeral identity and the sample doc_id."""
    monkeypatch.setenv("GUEST_SAMPLE_DOC_ID", "sample-goodfellow-ch2")
    get_settings.cache_clear()
    try:
        client = TestClient(app)
        res = client.post("/api/token", json={})
        assert res.status_code == 200

        body = res.json()
        assert body["identity"].startswith("guest-")

        payload = _decode_jwt_payload(body["token"])
        metadata = json.loads(payload["metadata"])
        assert metadata["active_doc_id"] == "sample-goodfellow-ch2"
        assert "user_id" not in metadata
    finally:
        get_settings.cache_clear()


def test_guest_token_with_explicit_doc_id_rejects_non_sample(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GUEST_SAMPLE_DOC_ID", "sample-goodfellow-ch2")
    get_settings.cache_clear()
    try:
        client = TestClient(app)
        res = client.post("/api/token", json={"doc_id": "my-custom-doc"})
        assert res.status_code == 403
    finally:
        get_settings.cache_clear()


def test_token_request_includes_user_id_and_active_doc_id(
    auth_client: TestClient,
    isolated_storage: Path,  # noqa: ARG001
) -> None:
    created = upload_pdf(auth_client, "owned.pdf")
    doc_id = created["doc_id"]

    res = auth_client.post("/api/token", json={"doc_id": doc_id})
    assert res.status_code == 200

    payload = _decode_jwt_payload(res.json()["token"])
    metadata = json.loads(payload["metadata"])
    assert metadata["active_doc_id"] == doc_id
    assert "user_id" in metadata


def test_token_request_without_doc_id_includes_user_id_only(auth_client: TestClient) -> None:
    res = auth_client.post("/api/token", json={})
    assert res.status_code == 200

    payload = _decode_jwt_payload(res.json()["token"])
    metadata = json.loads(payload["metadata"])
    assert metadata.keys() == {"user_id"}


def test_token_rejects_foreign_doc_id(
    auth_client: TestClient,
    isolated_storage: Path,  # noqa: ARG001
) -> None:
    other_client = make_auth_client("sub-other", "other@example.com")
    created = upload_pdf(other_client, "other.pdf")
    res = auth_client.post("/api/token", json={"doc_id": created["doc_id"]})
    assert res.status_code == 403
