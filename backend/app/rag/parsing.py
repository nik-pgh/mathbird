"""Normalized RAG parsing and retrieval models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Literal, Protocol, runtime_checkable

BlockType = Literal[
    "heading",
    "paragraph",
    "equation",
    "image",
    "graph",
    "table",
    "example",
    "exercise",
    "instruction",
    "unknown",
]


def _empty_mapping() -> Mapping[str, Any]:
    return MappingProxyType({})


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze_value(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, set | frozenset):
        return frozenset(_freeze_value(item) for item in value)
    return value


def _immutable_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType({key: _freeze_value(item) for key, item in value.items()})


@dataclass(frozen=True)
class ParsedBlock:
    block_id: str
    page_number: int
    block_type: BlockType
    text: str
    markdown: str = ""
    latex: str = ""
    image_refs: tuple[str, ...] = ()
    bbox: tuple[float, float, float, float] | None = None
    section_title: str = ""
    section_number: str = ""
    chapter_number: int = 0
    printed_page_number: int = 0
    exercise_number: str = ""
    example_number: str = ""
    figure_number: str = ""
    equation_number: str = ""
    neighboring_block_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "image_refs", tuple(self.image_refs))
        if self.bbox is not None:
            object.__setattr__(self, "bbox", tuple(self.bbox))
        object.__setattr__(self, "neighboring_block_ids", tuple(self.neighboring_block_ids))

    def content_for_embedding(self) -> str:
        parts = [self.markdown if self.markdown.strip() else self.text]
        if self.latex:
            parts.append(f"Equation: {self.latex}")
        if self.image_refs:
            parts.append("Visual references: " + ", ".join(self.image_refs))
        return "\n".join(part for part in parts if part.strip())

    def source_label(self, filename: str) -> str:
        label = filename
        if self.chapter_number:
            label += f", chapter {self.chapter_number}"
        if self.printed_page_number and self.printed_page_number != self.page_number:
            label += f", page {self.printed_page_number}"
        else:
            label += f", page {self.page_number}"
        if self.exercise_number:
            label += f", problem {self.exercise_number}"
        elif self.example_number:
            label += f", example {self.example_number}"
        elif self.figure_number:
            label += f", figure {self.figure_number}"
        elif self.equation_number:
            label += f", equation {self.equation_number}"
        elif self.section_number:
            label += f", section {self.section_number}"
        elif self.section_title:
            label += f", {self.section_title}"
        return label


@dataclass(frozen=True)
class ParsedPage:
    page_number: int
    text: str
    printed_page_number: int = 0
    blocks: tuple[ParsedBlock, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "blocks", tuple(self.blocks))


@dataclass(frozen=True)
class ParsedDocument:
    doc_id: str
    filename: str
    pages: tuple[ParsedPage, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "pages", tuple(self.pages))

    @property
    def page_count(self) -> int:
        return len(self.pages)


@dataclass(frozen=True)
class RetrievalRequest:
    query: str
    top_k: int = 4
    doc_ids: tuple[str, ...] = ()
    page_number: int | None = None
    chapter_number: int | None = None
    section_number: str = ""
    exercise_number: str = ""
    example_number: str = ""
    figure_number: str = ""
    equation_number: str = ""
    student_context: Mapping[str, Any] = field(default_factory=_empty_mapping)
    requested_modalities: tuple[str, ...] = ("text",)

    def __post_init__(self) -> None:
        object.__setattr__(self, "doc_ids", tuple(self.doc_ids))
        object.__setattr__(self, "student_context", _immutable_mapping(self.student_context))
        object.__setattr__(self, "requested_modalities", tuple(self.requested_modalities))


@dataclass(frozen=True)
class RetrievedRecord:
    text: str
    filename: str
    page_number: int
    score: float | None = None
    doc_id: str = ""
    block_id: str = ""
    block_type: BlockType = "unknown"
    exercise_number: str = ""
    example_number: str = ""
    figure_number: str = ""
    equation_number: str = ""
    section_number: str = ""
    section_title: str = ""
    chapter_number: int = 0
    printed_page_number: int = 0
    visual_refs: tuple[str, ...] = ()
    chunk_kind: str = ""
    source_block_types: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "visual_refs", tuple(self.visual_refs))
        object.__setattr__(self, "source_block_types", tuple(self.source_block_types))

    @property
    def source(self) -> str:
        label = self.filename
        if self.chapter_number:
            label += f", chapter {self.chapter_number}"
        if self.printed_page_number and self.printed_page_number != self.page_number:
            label += f", page {self.printed_page_number}"
        else:
            label += f", page {self.page_number}"
        if self.exercise_number:
            label += f", problem {self.exercise_number}"
        elif self.example_number:
            label += f", example {self.example_number}"
        elif self.figure_number:
            label += f", figure {self.figure_number}"
        elif self.equation_number:
            label += f", equation {self.equation_number}"
        elif self.section_number:
            label += f", section {self.section_number}"
        elif self.section_title:
            label += f", {self.section_title}"
        return label


@dataclass(frozen=True)
class RetrievedContext:
    records: tuple[RetrievedRecord, ...]
    citations: tuple[str, ...] = ()
    visual_refs: tuple[str, ...] = ()
    confidence: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "records", tuple(self.records))
        object.__setattr__(self, "citations", tuple(self.citations))
        object.__setattr__(self, "visual_refs", tuple(self.visual_refs))


@runtime_checkable
class TextbookParser(Protocol):
    async def parse_pdf(self, path: str, *, doc_id: str, filename: str) -> ParsedDocument: ...
