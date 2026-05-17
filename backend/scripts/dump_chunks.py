"""Dump (or grep) the full text of every chunk in Qdrant.

Use when you want to verify "is this content actually indexed?" by eye.
With ``--grep "substring"`` only prints chunks whose text contains the
substring (case-insensitive).

    uv run python -m scripts.dump_chunks
    uv run python -m scripts.dump_chunks --grep "plenty of paper"
    uv run python -m scripts.dump_chunks --grep legibility --doc-id <id>
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Any

from app.config import get_settings


def _decode(payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Return (metadata, text) for a Qdrant point payload."""
    if payload.get("_node_content"):
        try:
            from llama_index.core.vector_stores.utils import metadata_dict_to_node

            node = metadata_dict_to_node(payload)
            return dict(node.metadata or {}), node.get_content()
        except Exception:
            pass
    metadata = dict(payload.get("metadata") or payload)
    return metadata, str(payload.get("text") or payload.get("document") or "")


async def _amain(args: argparse.Namespace) -> None:
    settings = get_settings()
    print(f"Qdrant: {settings.qdrant_url}  collection={settings.qdrant_collection}")
    if args.doc_id:
        print(f"Filter: textbook_doc_id={args.doc_id}")
    if args.grep:
        print(f"Grep (case-insensitive substring): {args.grep!r}")

    from qdrant_client import AsyncQdrantClient
    from qdrant_client.http import models

    client = AsyncQdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
    )
    scroll_filter = None
    if args.doc_id:
        scroll_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="textbook_doc_id",
                    match=models.MatchValue(value=args.doc_id),
                )
            ]
        )

    needle = args.grep.lower() if args.grep else None
    matched = 0
    total = 0
    offset: Any = None
    try:
        while True:
            result = await client.scroll(
                collection_name=settings.qdrant_collection,
                scroll_filter=scroll_filter,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            batch, offset = result if isinstance(result, tuple) else (result, None)
            for point in batch:
                total += 1
                metadata, text = _decode(getattr(point, "payload", None) or {})
                if needle and needle not in text.lower():
                    continue
                matched += 1
                print(
                    f"\n--- page={metadata.get('page_number', '?')} "
                    f"block_type={metadata.get('block_type', '?')} "
                    f"ex#={metadata.get('exercise_number', '') or '-'} "
                    f"block_id={metadata.get('block_id', '?')} ---"
                )
                print(text)
            if not offset or not batch:
                break
    finally:
        close = getattr(client, "close", None)
        if close is not None:
            res = close()
            if hasattr(res, "__await__"):
                await res

    if needle:
        print(f"\n{matched}/{total} chunks matched {args.grep!r}")
    else:
        print(f"\n{total} chunks total")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--grep",
        default=None,
        help="Only print chunks whose text contains this substring (case-insensitive).",
    )
    parser.add_argument(
        "--doc-id",
        default=None,
        help="Only inspect points for this textbook_doc_id (default: all docs).",
    )
    args = parser.parse_args()
    asyncio.run(_amain(args))


if __name__ == "__main__":
    main()
