"""Syllabus tree persisted per uploaded document."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Problem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: Literal["exercise", "example"]
    label: str
    block_id: str
    page_number: int
    exercise_number: str = ""
    example_number: str = ""


class Concept(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    block_ids: tuple[str, ...] = ()
    problems: list[Problem] = Field(default_factory=list)


class Chapter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    number: int | None = None
    title: str
    concepts: list[Concept] = Field(default_factory=list)


class Syllabus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    version: Literal[1] = 1
    built_at: str
    chapters: list[Chapter] = Field(default_factory=list)
