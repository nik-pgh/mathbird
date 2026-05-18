"""Wire format for both whiteboard topics on the LiveKit data channel.

Schemas are pydantic so the LLM-facing ``@function_tool`` parameters get a
correct JSON Schema out of the box. The discriminated union on ``kind`` keeps
the LLM honest when it produces board items.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

AI_BOARD_TOPIC = "ai_board"
USER_BOARD_TOPIC = "user_board"


class AiBoardText(BaseModel):
    """A block of math/explanation text. ``markdown`` may contain $...$ LaTeX."""

    model_config = ConfigDict(extra="forbid")

    # No default on ``kind`` — discriminated-union dispatching from a JSON
    # dict (which is how the LLM's tool args reach us) needs the
    # discriminator field present in the JSON. With a default, pydantic
    # marks ``kind`` as optional in the JSON Schema, so OpenAI tells the
    # LLM it can omit it, and a missing ``kind`` then fails dispatch with
    # ``union_tag_not_found``.
    kind: Literal["text"]
    id: str = Field(description="Stable id; same id replaces, new id appends.")
    markdown: str


class AiBoardPlot(BaseModel):
    """A 1-D function plot rendered as inline SVG on the client."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["plot"]
    id: str
    expression: str = Field(description="Python-style expression in x, e.g. 'x**2 - 4'.")
    x_min: float = -10
    x_max: float = 10
    label: str | None = None


class AiBoardShape(BaseModel):
    """An arbitrary sanitized SVG fragment for simple diagrams."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["shape"]
    id: str
    svg: str = Field(description="SVG fragment without <svg> wrapper; client sanitizes.")


AiBoardItem = Annotated[
    AiBoardText | AiBoardPlot | AiBoardShape,
    Field(discriminator="kind"),
]


class AiBoardUpdate(BaseModel):
    """Server → clients update on the ``ai_board`` topic."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["upsert", "clear"]
    items: list[AiBoardItem] = Field(default_factory=list)


class UserBoardSnapshot(BaseModel):
    """Clients → server snapshot on the ``user_board`` topic."""

    model_config = ConfigDict(extra="forbid")

    png_b64: str = Field(description="Base64 PNG, ≤512px on the long edge.")
    captured_at_ms: int = Field(description="Client clock at capture time.")
    is_empty: bool = Field(default=False, description="True iff the board has been cleared.")
