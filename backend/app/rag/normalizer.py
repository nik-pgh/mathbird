"""Normalize LlamaParse structured output into stable textbook blocks."""

from __future__ import annotations

import re
from typing import Any

from app.rag.parsing import BlockType, ParsedBlock, ParsedDocument, ParsedPage

EXERCISE_RE = re.compile(r"\b(?:problem|exercise|question)\s+([A-Za-z]?\d+[A-Za-z]?)\b", re.I)
EXAMPLE_RE = re.compile(r"\bexample\s+([A-Za-z]?\d+[A-Za-z]?)\b", re.I)
EQUATION_RE = re.compile(r"(\$\$.*?\$\$|\$.*?\$|\\\(|\\\[|\\begin\{equation\})", re.S)


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _page_number(page: Any, fallback: int) -> int:
    value = _get(page, "page", None) or _get(page, "page_number", None) or _get(
        page,
        "page_index",
        None,
    )
    if value is None:
        return fallback
    return int(value)


def _item_text(item: Any) -> str:
    return str(_get(item, "value", "") or _get(item, "text", "") or "").strip()


def _item_markdown(item: Any) -> str:
    return str(_get(item, "md", "") or _get(item, "markdown", "") or _item_text(item)).strip()


def _classify_item(item: Any, text: str, markdown: str) -> BlockType:
    item_type = str(_get(item, "type", "") or "").lower()
    haystack = f"{text}\n{markdown}"

    if item_type == "heading":
        return "heading"
    if item_type in {"image", "figure"}:
        return "image"
    if item_type == "table":
        return "table"
    if EXERCISE_RE.search(haystack):
        return "exercise"
    if EXAMPLE_RE.search(haystack):
        return "example"
    if EQUATION_RE.search(haystack):
        return "equation"
    if item_type == "text":
        return "paragraph"
    return "unknown"


def _exercise_number(text: str, markdown: str) -> str:
    match = EXERCISE_RE.search(f"{text}\n{markdown}")
    return match.group(1) if match else ""


def _image_refs(item: Any, doc_id: str) -> tuple[str, ...]:
    names: list[str] = []
    direct = _get(item, "image_filename", "")
    if direct:
        names.append(str(direct))

    markdown = _item_markdown(item)
    names.extend(re.findall(r"!\[[^\]]*\]\(([^)]+)\)", markdown))

    return tuple(f"{doc_id}:{name}" for name in dict.fromkeys(names))


def _bbox(item: Any) -> tuple[float, float, float, float] | None:
    boxes = _get(item, "bbox", None)
    if not boxes:
        return None
    first = boxes[0] if isinstance(boxes, list) else boxes
    x = float(_get(first, "x", 0))
    y = float(_get(first, "y", 0))
    w = float(_get(first, "w", 0))
    h = float(_get(first, "h", 0))
    return (x, y, w, h)


def normalize_llamaparse_items(payload: Any, *, doc_id: str, filename: str) -> ParsedDocument:
    items = _get(payload, "items", {}) or {}
    pages_payload = _get(items, "pages", []) or []
    pages: list[ParsedPage] = []

    for page_index, page_payload in enumerate(pages_payload, start=1):
        page_number = _page_number(page_payload, page_index)
        raw_items = _get(page_payload, "items", []) or []
        blocks: list[ParsedBlock] = []
        current_section = ""

        for item in raw_items:
            text = _item_text(item)
            markdown = _item_markdown(item)
            if not text and not markdown:
                continue

            block_type = _classify_item(item, text, markdown)
            if block_type == "heading":
                current_section = text or markdown.lstrip("#").strip()

            block_id = f"{doc_id}:p{page_number}:b{len(blocks)}"
            previous_block_id = blocks[-1].block_id if blocks else ""
            neighboring_block_ids = (previous_block_id,) if previous_block_id else ()

            blocks.append(
                ParsedBlock(
                    block_id=block_id,
                    page_number=page_number,
                    block_type=block_type,
                    text=text or markdown,
                    markdown=markdown,
                    latex=markdown if block_type == "equation" else "",
                    image_refs=_image_refs(item, doc_id),
                    bbox=_bbox(item),
                    section_title=current_section,
                    exercise_number=_exercise_number(text, markdown),
                    neighboring_block_ids=neighboring_block_ids,
                )
            )

        pages.append(
            ParsedPage(
                page_number=page_number,
                text="\n\n".join(block.text for block in blocks),
                blocks=blocks,
            )
        )

    return ParsedDocument(doc_id=doc_id, filename=filename, pages=pages)
