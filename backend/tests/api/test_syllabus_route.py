"""Tests for syllabus storage and GET route."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.rag import retriever as retriever_mod
from app.storage import base as storage_mod
from app.syllabus.models import Chapter, Concept, Problem, Syllabus
from app.syllabus.store import load_syllabus, save_syllabus, syllabus_key


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_DIR", str(tmp_path))
    monkeypatch.setenv("RAG_PROVIDER", "null")
    get_settings.cache_clear()
    storage_mod.get_storage.cache_clear()
    retriever_mod._singleton = None
    yield tmp_path
    get_settings.cache_clear()
    storage_mod.get_storage.cache_clear()
    retriever_mod._singleton = None


def _sample_syllabus(doc_id: str) -> Syllabus:
    return Syllabus(
        doc_id=doc_id,
        built_at="2026-06-19T00:00:00+00:00",
        chapters=[
            Chapter(
                id="ch-1",
                number=1,
                title="Chapter 1",
                concepts=[
                    Concept(
                        id="ch-1-c-intro",
                        title="Intro",
                        problems=[
                            Problem(
                                id="ch-1-p-1",
                                kind="exercise",
                                label="Problem 1",
                                block_id="doc-1:p1:b0",
                                page_number=1,
                            )
                        ],
                    )
                ],
            )
        ],
    )


@pytest.mark.asyncio
async def test_save_and_load_syllabus_round_trip(isolated_storage: Path) -> None:
    storage = storage_mod.get_storage()
    syllabus = _sample_syllabus("doc-abc")
    await save_syllabus(storage, "doc-abc", syllabus)

    path = isolated_storage / syllabus_key("doc-abc")
    assert path.exists()

    loaded = await load_syllabus(storage, "doc-abc")
    assert loaded is not None
    assert loaded.chapters[0].concepts[0].problems[0].label == "Problem 1"


def test_get_syllabus_route_returns_tree(auth_client: TestClient, isolated_storage: Path) -> None:
    doc_id = "doc-abc"
    path = isolated_storage / syllabus_key(doc_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    syllabus = _sample_syllabus(doc_id)
    path.write_text(json.dumps(syllabus.model_dump(mode="json")), encoding="utf-8")

    res = auth_client.get(f"/api/documents/{doc_id}/syllabus")
    assert res.status_code == 200
    assert res.json()["chapters"][0]["title"] == "Chapter 1"


def test_get_syllabus_route_404_when_missing(auth_client: TestClient) -> None:
    res = auth_client.get("/api/documents/missing/syllabus")
    assert res.status_code == 404
