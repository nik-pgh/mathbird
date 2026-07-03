"""Document catalog listing rules."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import get_settings
from app.documents.catalog import is_document_storage_key, list_document_summaries
from app.storage import base as storage_mod


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("goodfellow-ch2/deep_learning.pdf", True),
        ("6f8de7c2bacb4083829a376ba97d43f3/hscc_srh_0101.pdf", True),
        ("goodfellow-ch2/meta.json", False),
        ("goodfellow-ch2/syllabus.json", False),
        ("user-1/doc-1/progress.json", False),
        ("20574461-5aaa-4b45-93ae-95ea11d66e9f/goodfellow-ch2/progress.json", False),
        ("orphan", False),
    ],
)
def test_is_document_storage_key(key: str, expected: bool) -> None:
    assert is_document_storage_key(key) is expected


@pytest.mark.asyncio
async def test_list_document_summaries_ignores_progress_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_DIR", str(tmp_path))
    get_settings.cache_clear()
    storage_mod.get_storage.cache_clear()

    doc_id = "goodfellow-ch2"
    doc_dir = tmp_path / doc_id
    doc_dir.mkdir()
    (doc_dir / "chapter.pdf").write_bytes(b"%PDF-1.4\n")
    (doc_dir / "meta.json").write_text(
        json.dumps({"indexed": True}),
        encoding="utf-8",
    )

    progress_dir = tmp_path / "user-1" / doc_id
    progress_dir.mkdir(parents=True)
    (progress_dir / "progress.json").write_text("{}", encoding="utf-8")

    summaries = await list_document_summaries()

    assert [s.doc_id for s in summaries] == [doc_id]
    assert summaries[0].filename == "chapter.pdf"

    get_settings.cache_clear()
    storage_mod.get_storage.cache_clear()
