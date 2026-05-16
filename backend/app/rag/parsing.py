"""Normalized RAG parsing and retrieval models."""

from __future__ import annotations

from dataclasses import dataclass, field
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

    def content_for_embedding(self) -> str:
        parts = [self.markdown or self.text]
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
    blocks: list[ParsedBlock] = field(default_factory=list)


@dataclass(frozen=True)
class ParsedDocument:
    doc_id: str
    filename: str
    pages: list[ParsedPage] = field(default_factory=list)

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
    student_context: dict[str, Any] = field(default_factory=dict)
    requested_modalities: tuple[str, ...] = ("text",)


@dataclass(frozen=True)
class RetrievedRecord:
    text: str
    filename: str
    page_number: int
    score: float | None = None
    doc_id: str = ""
    block_id: str = ""
    block_type: str = "unknown"
    exercise_number: str = ""
    section_title: str = ""
    visual_refs: tuple[str, ...] = ()

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
    records: list[RetrievedRecord]
    citations: tuple[str, ...] = ()
    visual_refs: tuple[str, ...] = ()
    confidence: float | None = None


@runtime_checkable
class TextbookParser(Protocol):
    async def parse_pdf(self, path: str, *, doc_id: str, filename: str) -> ParsedDocument: ...
