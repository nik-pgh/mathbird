"""Parse PDFs into ParsedDocument for syllabus building."""

from __future__ import annotations

from pathlib import Path

from app.config import Settings, get_settings
from app.rag.multi_ingest import build_parser
from app.rag.parsing import ParsedDocument


async def parse_pdf_to_document(
    path: str,
    *,
    doc_id: str,
    settings: Settings | None = None,
) -> ParsedDocument:
    base = settings or get_settings()
    parser = build_parser(base)
    filename = Path(path).name
    return await parser.parse_pdf(path, doc_id=doc_id, filename=filename)
