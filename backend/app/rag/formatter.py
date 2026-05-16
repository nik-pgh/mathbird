"""Format retrieved records into the public Retriever result shape."""

from __future__ import annotations

from app.rag.parsing import RetrievedRecord
from app.rag.retriever import RetrievedChunk


def format_records_as_chunks(records: list[RetrievedRecord]) -> list[RetrievedChunk]:
    seen: set[str] = set()
    chunks: list[RetrievedChunk] = []

    for record in records:
        dedupe_key = record.block_id or f"{record.source}:{record.text}"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        text = record.text.strip()
        if not text:
            continue

        chunks.append(
            RetrievedChunk(
                text=text,
                source=record.source,
                score=record.score,
            )
        )

    return chunks
