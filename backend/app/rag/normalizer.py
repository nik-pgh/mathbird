"""Normalize LlamaParse structured output into stable textbook blocks."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import unquote, urlparse

from app.rag.chapter import parse_chapter_number
from app.rag.parsing import BlockType, ParsedBlock, ParsedDocument, ParsedPage
from app.rag.reference_ids import (
    EXAMPLE_RE,
    EXERCISE_LABEL_RE,
    EXERCISE_LIST_RE,
    extract_equation_number,
    extract_example_number,
    extract_exercise_number,
    extract_figure_number,
    parse_section_number,
)

EQUATION_RE = re.compile(r"(\$\$.*?\$\$|\$.*?\$|\\\(|\\\[|\\begin\{equation\})", re.S)
EXERCISE_RE = re.compile(
    rf"{EXERCISE_LABEL_RE.pattern}|{EXERCISE_LIST_RE.pattern}",
    re.I,
)


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _page_number(page: Any, fallback: int) -> int:
    value = (
        _get(page, "page", None)
        or _get(page, "page_number", None)
        or _get(
            page,
            "page_index",
            None,
        )
    )
    if value is None:
        return fallback
    return int(value)


def _printed_page_number(page: Any, *, pdf_page_number: int) -> int:
    for key in (
        "printed_page_number",
        "printed_page",
        "printedPageNumber",
        "page_label",
        "pageLabel",
    ):
        value = _get(page, key, None)
        if value is None:
            continue
        if isinstance(value, int | float):
            return int(value)
        digits = re.search(r"\d+", str(value))
        if digits:
            return int(digits.group())
    return pdf_page_number


def _pages_payload(payload: Any) -> Any:
    items = _get(payload, "items", None)
    pages = _get(items, "pages", None) if items is not None else None
    return pages or _get(payload, "pages", []) or []


def _item_text(item: Any) -> str:
    return str(_get(item, "value", "") or _get(item, "text", "") or "").strip()


def _item_markdown(item: Any) -> str:
    return str(_get(item, "md", "") or _get(item, "markdown", "") or _item_text(item)).strip()


def _classify_item(item: Any, text: str, markdown: str) -> BlockType:
    item_type = str(_get(item, "type", "") or "").lower()
    haystack = f"{text}\n{markdown}"

    if EXAMPLE_RE.search(haystack):
        return "example"
    if EXERCISE_RE.search(haystack):
        return "exercise"
    if item_type == "heading":
        return "heading"
    if item_type in {"image", "figure"}:
        return "image"
    if item_type == "table":
        return "table"
    if EQUATION_RE.search(haystack):
        return "equation"
    if item_type == "text":
        return "paragraph"
    return "unknown"


def _stable_ref_name(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""

    parsed = urlparse(raw)
    path = parsed.path if parsed.scheme or parsed.netloc else raw.split("?", 1)[0]
    path = unquote(path).rstrip("/")
    return path.rsplit("/", 1)[-1] if path else ""


def _page_image_names(page: Any) -> tuple[str, ...]:
    names: list[str] = []
    for image in _get(page, "images", []) or []:
        name = _stable_ref_name(_get(image, "name", "")) or _stable_ref_name(
            _get(image, "filename", ""),
        )
        if name:
            names.append(name)
    return tuple(dict.fromkeys(names))


def _image_refs(item: Any, doc_id: str, page_image_name: str = "") -> tuple[str, ...]:
    names: list[str] = []
    direct = _get(item, "image_filename", "")
    if direct:
        names.append(_stable_ref_name(direct))

    markdown = _item_markdown(item)
    names.extend(
        _stable_ref_name(match) for match in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", markdown)
    )

    if not names and page_image_name:
        names.append(page_image_name)

    return tuple(f"{doc_id}:{name}" for name in dict.fromkeys(name for name in names if name))


def _bbox(item: Any) -> tuple[float, float, float, float] | None:
    boxes = _get(item, "bbox", None) or _get(item, "bBox", None)
    if not boxes:
        return None
    first = boxes[0] if isinstance(boxes, list) else boxes
    values = (
        _get(first, "x", None),
        _get(first, "y", None),
        _get(first, "w", None),
        _get(first, "h", None),
    )
    if any(value is None for value in values):
        return None
    return tuple(float(value) for value in values)


def _block_reference_ids(text: str, markdown: str, *, block_type: BlockType) -> dict[str, str]:
    haystack = f"{text}\n{markdown}"
    return {
        "exercise_number": extract_exercise_number(
            haystack,
            allow_list_style=block_type == "exercise",
        ),
        "example_number": extract_example_number(haystack),
        "figure_number": extract_figure_number(haystack),
        "equation_number": extract_equation_number(haystack),
    }


def normalize_llamaparse_items(payload: Any, *, doc_id: str, filename: str) -> ParsedDocument:
    pages_payload = _pages_payload(payload)
    pages: list[ParsedPage] = []
    current_section = ""
    current_section_number = ""
    current_chapter = 0

    for page_index, page_payload in enumerate(pages_payload, start=1):
        page_number = _page_number(page_payload, page_index)
        printed_page_number = _printed_page_number(
            page_payload,
            pdf_page_number=page_number,
        )
        raw_items = _get(page_payload, "items", []) or []
        page_image_names = _page_image_names(page_payload)
        page_image_index = 0
        blocks: list[ParsedBlock] = []

        for item in raw_items:
            text = _item_text(item)
            markdown = _item_markdown(item)
            if not text and not markdown:
                continue

            block_type = _classify_item(item, text, markdown)
            heading_text = text or markdown.lstrip("#").strip()
            if block_type == "heading":
                current_section = heading_text

            detected_chapter = parse_chapter_number(f"{text}\n{markdown}")
            if detected_chapter is not None:
                current_chapter = detected_chapter

            reference_ids = _block_reference_ids(text, markdown, block_type=block_type)
            section_from_text = parse_section_number(f"{text}\n{markdown}")
            section_number = section_from_text or current_section_number
            if section_from_text:
                current_section_number = section_from_text

            block_id = f"{doc_id}:p{page_number}:b{len(blocks)}"
            previous_block_id = blocks[-1].block_id if blocks else ""
            neighboring_block_ids = (previous_block_id,) if previous_block_id else ()
            page_image_name = ""
            if block_type == "image" and page_image_index < len(page_image_names):
                page_image_name = page_image_names[page_image_index]
                page_image_index += 1

            blocks.append(
                ParsedBlock(
                    block_id=block_id,
                    page_number=page_number,
                    block_type=block_type,
                    text=text or markdown,
                    markdown=markdown,
                    latex=markdown if block_type == "equation" else "",
                    image_refs=_image_refs(item, doc_id, page_image_name),
                    bbox=_bbox(item),
                    section_title=current_section,
                    section_number=section_number,
                    chapter_number=current_chapter,
                    printed_page_number=printed_page_number,
                    exercise_number=reference_ids["exercise_number"],
                    example_number=reference_ids["example_number"],
                    figure_number=reference_ids["figure_number"],
                    equation_number=reference_ids["equation_number"],
                    neighboring_block_ids=neighboring_block_ids,
                )
            )

        pages.append(
            ParsedPage(
                page_number=page_number,
                printed_page_number=printed_page_number,
                text="\n\n".join(block.text for block in blocks),
                blocks=blocks,
            )
        )

    return ParsedDocument(doc_id=doc_id, filename=filename, pages=pages)
