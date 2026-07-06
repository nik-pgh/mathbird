"""``OpenAIBoardExtractor`` — board extractor backed by OpenAI structured
outputs.

The vendor SDK import lives only in this file; the rest of the agent uses
the duck-typed :class:`BoardExtractor` Protocol.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.agent.whiteboard.messages import (
    AiBoardDiagram,
    AiBoardItem,
    AiBoardPlot,
    AiBoardShape,
    AiBoardText,
)

logger = logging.getLogger("mathbird.agent.extractor")


# OpenAI's Structured Outputs API rejects ``oneOf`` JSON Schema, which is
# what pydantic emits for the ``AiBoardItem`` discriminated union
# (``Annotated[... , Field(discriminator="kind")]``). For the response
# schema only, use a plain Union of the concrete classes — pydantic emits
# ``anyOf`` for plain unions, which OpenAI accepts. Runtime validation
# behaves the same because the ``Literal[...]`` constraints on ``kind``
# uniquely identify each variant.
_ExtractorItem = AiBoardText | AiBoardPlot | AiBoardShape | AiBoardDiagram


class ExtractorResponse(BaseModel):
    items: list[_ExtractorItem]


_SYSTEM_PROMPT = """\
You extract whiteboard items from a single sentence of a math tutor's
spoken reply. The tutor is explaining math to a student in a live voice
session. Tutor cards appear automatically from speech — the tutor expects
you to capture teaching visuals proactively.

You will receive:
- The sentence the tutor just said.
- The previous sentence (for continuation/revision context).
- The list of items already on the whiteboard (with their ids).

Emit zero or more AiBoardItem entries that should appear on the board.
Be proactive during teaching — emit items when the sentence introduces
or continues visual math the student should see. Prefer showing key
equations, function plots, and diagrams during explanations, definitions,
worked examples, comparisons, and explicit draw/show requests.

- text: a standalone equation, an expression being algebraically manipulated,
  or a named concept the student should remember. Wrap math in $...$ LaTeX.
    Example sentence: "let's set up 2x + 5 = 10"
    → {"kind": "text", "id": "eq1", "markdown": "$2x + 5 = 10$"}
    Example sentence: "subtract 5 from both sides to get 2x = 5"
    → {"kind": "text", "id": "eq1", "markdown": "$2x + 5 = 10$ \\\\ $2x = 5$"}
       (id reused, prior content extended — see ID policy below)
    Example sentence: "the definition is: a function maps each input to
    exactly one output"
    → {"kind": "text", "id": "def1",
       "markdown": "**Function** — maps each input to exactly one output."}

- plot: a single-variable function the student should SEE GRAPHED. Emit a
  plot whenever the tutor's words point at a function as a visual/curve —
  not just an equation to read. Trigger on any of: "plot/graph y = …",
  "the parabola/curve y = …", "show me y = …", "y = … opens upward / is
  increasing", a named shape ("parabola", "sine wave", "line"), or a
  bounded window ("from -π to π"). In all of these, emit a PLOT item with
  the Python expression for f(x) — NOT a text item showing the equation,
  and NOT a hand-drawn SVG. Plot is the DEFAULT for function mentions;
  reserving text for functions is a misclassification.

  IMPORTANT — never hand-draw a function curve yourself, and never reduce a
  function to a text equation. When the tutor's words describe a curve or
  graph of y = f(x), there are only two correct responses: emit a `plot`
  with the Python `expression` (the renderer graphs it), or emit nothing.
  Do NOT produce a `shape` item with an SVG <path> approximating the curve
  (that loses the equation and freezes the figure), and do NOT produce a
  `text` item with "$y = f(x)$" (the student needs the graph, not the
  formula re-typeset). The whole point of the board is the visual.
  Always set a descriptive `label` (the spoken function name or form,
  LaTeX ok) and set `x_min`/`x_max` when the tutor mentions a window.
    Example sentence: "let me show you, y = x squared"
    → {"kind": "plot", "id": "p1", "expression": "x**2",
       "label": "Parabola: $y = x^2$"}
    Example sentence: "the parabola y = x squared opens upward"
    → {"kind": "plot", "id": "p1", "expression": "x**2",
       "label": "Parabola: $y = x^2$"}
    Example sentence: "let's plot y = sin(x) from -π to π"
    → {"kind": "plot", "id": "p2", "expression": "sin(x)",
       "x_min": -3.14, "x_max": 3.14, "label": "Sine: $y = \\sin(x)$"}

  Use text (NOT plot) when:
  - The equation is being algebraically manipulated as a step in a
    derivation (e.g., "2x + 5 = 10" being solved).
  - The function is multi-variable (z = x*y) or not easily plottable in
    one variable.
  - The agent mentions a function NAME in passing without any curve/graph
    intent (e.g., "do you remember the quadratic formula?"). Note: "show
    me y = x squared" or "the parabola y = …" IS curve intent — route to
    plot, not text.

- diagram: a structured visual relationship that Mermaid can express well:
  factor trees, flowcharts, step diagrams, boxes/arrows, relationship diagrams,
  concept maps, comparison trees, and simple neural-network layer stacks.
  Use Mermaid source with syntax="mermaid". Prefer "flowchart TD" or
  "flowchart LR". Be FAITHFUL and COMPLETE — the diagram must reflect the
  full structure of what the tutor described, not a teaser of it. Every
  item, step, branch, factor, or layer the tutor named must appear as its
  own node; never collapse a multi-step process into two boxes or stop a
  factor tree before it reaches primes. Include a descriptive `label`.
    Example sentence: "draw a factor tree for 42"
    → {"kind": "diagram", "id": "d1", "syntax": "mermaid",
       "source": "flowchart TD\\n  n42[42] --> n2[2]\\n  n42 --> n21[21]\\n  n21[21] --> n3[3]\\n  n21[21] --> n7[7]",
       "label": "Factor tree for 42: $2 \\\\cdot 3 \\\\cdot 7$"}
    Example sentence: "picture a tiny network: input, hidden, output"
    → {"kind": "diagram", "id": "d2", "syntax": "mermaid",
       "source": "flowchart LR\\n  IN[input] --> H[hidden] --> OUT[output]",
       "label": "Simple network: input → hidden → output"}
    Example sentence: "draw a flowchart: start, compute delta, check sign, stop"
    → {"kind": "diagram", "id": "d3", "syntax": "mermaid",
       "source": "flowchart TD\\n  S[start] --> D[compute delta]\\n  D --> C{check sign}\\n  C -- yes --> U[update]\\n  C -- no --> E[stop]\\n  U --> E",
       "label": "Gradient descent steps"}
  In the last example, note that EVERY spoken step (start, compute delta,
  check sign, stop) becomes a node, and a decision branch the tutor
  described becomes a branching edge. Do the same: turn each enumerated
  step or branch into its own node.

- shape: a freeform SVG sketch for visuals the parametric plot renderer
  CANNOT handle: geometry figures (triles, circles, angles), number lines
  with tick marks/labels, fraction/area models, bar models, and anything
  needing precise 2-D placement of multiple labeled elements. Use simple SVG
  primitives only and omit the outer <svg> wrapper. shape is the escape
  hatch for non-function figures — do NOT use it to draw a function curve;
  that is always a `plot` (see the routing rule above).
    Example sentence: "draw a number line from 0 to 6"
    → {"kind": "shape", "id": "s1",
       "svg": "<line x1='0' y1='50' x2='100' y2='50' stroke='currentColor'/>"}

For explicit draw/show/diagram requests, use diagram or shape instead of text
when the requested content can be visualized. Keep plot for functions and keep
text for explanations, equations, and algebraic derivation steps.

Do NOT emit items ONLY for:

- Pure Socratic questions with no new math to show:
    "What happens when x is zero?"        → []
    "Does the rule p → q apply here?"     → []
    "What's the next step?"               → []

- Casual numeric references (numbers that aren't being computed or shown):
    "There are 3 cases to consider."      → []
    "Let's start with part (a)."          → []

- Meta-commentary with no new content:
    "As we saw above..."                  → []
    "Look at the board again."            → []

- Conversational filler:
    "Nice work."  "Let's see."  "Okay."  "Right, exactly."  "Hmm."   → []

- Restatement of an existing board item without revision:
    Current: $2x + 5 = 10$
    Sentence: "So we have 2x + 5 = 10."     → []
    (Don't re-emit; the item is already on the board.)

ID policy — ACCUMULATE BY DEFAULT:

If the current sentence continues work on the SAME problem or concept that
already has an item on the board (a derivation step, an explanation of
parts of one equation, a revision of a prior step, OR adding context to a
curve already plotted), REUSE that item's existing id and EXTEND its
content rather than appending a new item:

  - For text items: append the new content to the existing markdown,
    separated by `\\\\` (LaTeX line break for stacked equations) or by
    `\\n\\n` for separate paragraphs of explanation.
  - For plot items: update the expression / bounds / label as needed,
    keeping the same id.

Mint a FRESH id only when the topic CLEARLY changes — the agent has
moved from one problem to a different one, or pivoted from algebra to
geometry, or started a separate worked example.

For new items, pick the next id in a stable sequence:
  text items: eq1, eq2, eq3, ...
  plot items: p1, p2, p3, ...
  shape items: s1, s2, s3, ...
  diagram items: d1, d2, d3, ...
Inspect the current items list (passed in the user message) to determine
which ids are already taken.

Never produce two items with the same id in one response.

When the sentence teaches, defines, plots, or diagrams something concrete,
emit the matching item. Reserve an empty list for pure questions, filler,
and exact restatements only.
"""


def _format_user_message(
    sentence: str,
    current_items: list[AiBoardItem],
    last_sentence: str | None,
) -> str:
    items_json = json.dumps(
        [item.model_dump() for item in current_items],
        ensure_ascii=False,
    )
    prev = last_sentence if last_sentence else "(none)"
    return (
        f"Current board items (JSON):\n{items_json}\n\n"
        f"Previous sentence: {prev}\n\n"
        f"Sentence to process: {sentence}"
    )


class OpenAIBoardExtractor:
    def __init__(
        self,
        *,
        model: str,
        timeout: float,
        api_key: str | None = None,
        client: Any | None = None,
    ) -> None:
        self._model = model
        self._timeout = timeout
        # ``client`` injection is used by unit tests; in production we
        # build an ``AsyncOpenAI`` client.
        self._client = client if client is not None else AsyncOpenAI(api_key=api_key)

    async def extract(
        self,
        sentence: str,
        current_items: list[AiBoardItem],
        last_sentence: str | None,
    ) -> list[AiBoardItem]:
        try:
            completion = await asyncio.wait_for(
                self._client.beta.chat.completions.parse(
                    model=self._model,
                    response_format=ExtractorResponse,
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": _format_user_message(sentence, current_items, last_sentence),
                        },
                    ],
                ),
                timeout=self._timeout,
            )
        except TimeoutError:
            logger.warning(
                "board extractor timed out after %.2fs on sentence: %r",
                self._timeout,
                sentence[:80],
            )
            return []
        except Exception as exc:
            logger.warning(
                "board extractor call failed (%s); skipping sentence: %r",
                type(exc).__name__,
                sentence[:80],
            )
            return []

        try:
            parsed = completion.choices[0].message.parsed
        except (AttributeError, IndexError):
            logger.warning("board extractor returned malformed completion shape")
            return []

        if parsed is None:
            return []
        return list(parsed.items)
