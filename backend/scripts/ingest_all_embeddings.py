"""Ingest one PDF into every embedding collection (parse once).

LlamaParse runs a single time; each provider/model pair gets its own Qdrant
collection via ``QDRANT_COLLECTION=auto``.

Run from ``backend/``::

    uv run python -m scripts.ingest_all_embeddings \\
        ../materials/deep_learning_ian_goodfellow_chapter_2.pdf \\
        --doc-id goodfellow-ch2

    # Subset of models only
    uv run python -m scripts.ingest_all_embeddings book.pdf \\
        --target openai:text-embedding-3-small \\
        --target voyage:voyage-3-lite

    # Avoid parallel embedding API calls (slower, gentler on rate limits)
    uv run python -m scripts.ingest_all_embeddings book.pdf --sequential
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from app.config import EmbeddingProvider, get_settings
from app.rag.embeddings import embedding_collection_name
from app.rag.multi_ingest import DEFAULT_EMBEDDING_TARGETS, ingest_pdf_all_embeddings


def _parse_target(raw: str) -> tuple[EmbeddingProvider, str]:
    if ":" not in raw:
        raise argparse.ArgumentTypeError(
            f"Expected provider:model, got {raw!r}. "
            "Example: openai:text-embedding-3-small"
        )
    provider, model = raw.split(":", 1)
    provider = provider.strip()
    model = model.strip()
    if not provider or not model:
        raise argparse.ArgumentTypeError(f"Invalid target {raw!r}")
    return provider, model  # type: ignore[return-value]


def _default_doc_id(path: Path) -> str:
    slug = path.stem.lower()
    cleaned = "".join(ch if ch.isalnum() else "-" for ch in slug).strip("-")
    return cleaned or "document"


async def _amain(args: argparse.Namespace) -> int:
    pdf_path = Path(args.pdf).expanduser().resolve()
    if not pdf_path.is_file():
        print(f"PDF not found: {pdf_path}", file=sys.stderr)
        return 1

    doc_id = args.doc_id or _default_doc_id(pdf_path)
    targets = tuple(args.target) if args.target else DEFAULT_EMBEDDING_TARGETS
    settings = get_settings()

    print(f"PDF: {pdf_path}")
    print(f"doc_id: {doc_id}")
    print(f"Qdrant: {settings.qdrant_url}")
    print(f"Targets ({len(targets)}):")
    for provider, model in targets:
        print(f"  {provider}:{model} -> {embedding_collection_name(provider, model)}")
    print(f"Mode: {'parallel' if args.parallel else 'sequential'}")
    print()

    results = await ingest_pdf_all_embeddings(
        str(pdf_path),
        doc_id=doc_id,
        targets=targets,
        parallel=args.parallel,
    )

    print("Done:")
    for result in results:
        print(
            f"  {result.embedding_provider}/{result.embedding_model} "
            f"-> {result.collection_name} ({result.node_count} nodes)"
        )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", help="Path to the PDF file to ingest.")
    parser.add_argument(
        "--doc-id",
        default=None,
        help="Stable document id stored in Qdrant metadata (default: slug from filename).",
    )
    parser.add_argument(
        "--target",
        action="append",
        type=_parse_target,
        metavar="PROVIDER:MODEL",
        help=(
            "Embedding pair to index (repeatable). "
            "Default: all six documented models from .env.example."
        ),
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Insert into collections one at a time instead of in parallel.",
    )
    args = parser.parse_args()
    args.parallel = not args.sequential
    raise SystemExit(asyncio.run(_amain(args)))


if __name__ == "__main__":
    main()
