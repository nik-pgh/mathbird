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


def _immutable_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(value))


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
    exercise_number: str = ""
    neighboring_block_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "image_refs", tuple(self.image_refs))
        object.__setattr__(self, "neighboring_block_ids", tuple(self.neighboring_block_ids))

    def content_for_embedding(self) -> str:
        parts = [self.markdown if self.markdown.strip() else self.text]
        if self.latex:
            parts.append(f"Equation: {self.latex}")
        if self.image_refs:
            parts.append("Visual references: " + ", ".join(self.image_refs))
        return "\n".join(part for part in parts if part.strip())

    def source_label(self, filename: str) -> str:
        label = f"{filename}, page {self.page_number}"
        if self.exercise_number:
            label += f", problem {self.exercise_number}"
        elif self.section_title:
            label += f", {self.section_title}"
        return label


@dataclass(frozen=True)
class ParsedPage:
    page_number: int
    text: str
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
    exercise_number: str = ""
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
    section_title: str = ""
    visual_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "visual_refs", tuple(self.visual_refs))

    @property
    def source(self) -> str:
        label = f"{self.filename}, page {self.page_number}"
        if self.exercise_number:
            label += f", problem {self.exercise_number}"
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
