# Board Card Controls Design

## Summary

Add a top-right Student Card control, support multiple student handwriting cards, make tutor cards use the right visual type for text, graphs, and diagrams, and improve tutor-card placement so new cards appear in available space instead of a fixed spawn position.

This work changes both frontend board behavior and the backend user-board contract. The current backend stores one latest student-board reading, which is not enough once the student can create multiple handwriting cards. The new contract should preserve the existing data-channel topic while adding a card id to snapshots and combining per-card readings for the tutor.

## Goals

- Let the student add another handwriting card from a top-right board control.
- Keep each student card the same kind of surface as the current Student Card: draggable, resizable, drawable, clearable, and OCR-readable.
- Let the tutor see readings from all non-empty student cards, labeled by card.
- Make tutor `text` items look and read as text cards, not equation cards.
- Strengthen the board extractor so explicit diagram requests produce visual cards instead of text descriptions.
- Add Mermaid-backed tutor diagram cards for structured diagrams where Mermaid is a good fit.
- Keep graph support through existing `plot` cards.
- Place new tutor cards and new student cards in available board space when possible.
- Stop tutor cards from shrinking when dragged far to the right.

## Non-Goals

- No persistent saved board across reloads.
- No multi-user synchronization of manually moved card positions beyond the existing LiveKit room state.
- No rich typed student note card in this pass; "Student Card" means a handwriting card.
- No arbitrary freeform SVG editor for the student.
- No full layout solver; placement should be deterministic and good enough for common card counts.

## Current State

The whiteboard wire model already supports tutor `text`, `plot`, and `shape` items. The frontend renders those through `BoardItem`, but the object chrome labels `text` as "Equation", which makes normal explanation cards feel wrong.

The OpenAI board extractor has detailed positive rules for text and plot, but it does not have comparable diagram rules. As a result, when the tutor says "draw a diagram", the extractor can reasonably default to a text card because no strong instruction tells it to create a visual item.

The frontend workspace has one `handwriting` state object. The backend `BoardState` also stores one latest `user_text`. Multiple student cards require changing both sides to track card ids.

New tutor cards currently spawn from `defaultObjectPosition(index)`, a fixed two-column formula. The function does not check existing tutor objects, the handwriting card, or overlays. Tutor-card CSS also uses `min-width` and `max-width` without a stable width, so content can reflow and appear to shrink as cards move near visible extents.

## UX Design

The board gets a compact top-right control labeled `Student Card`. It should be visually part of board chrome, not the global app topbar. Clicking it creates a new handwriting card with the next label, such as `Student Card 2`, and places it in open board space.

Student cards keep the existing drawing tools: pen, eraser, undo, clear, drag handle, and resize handle. The first default card remains present when a session starts. Added cards behave the same way and publish snapshots independently.

Tutor cards use source-aware chrome:

- `text`: title `Tutor Card`, kind pill `Text`
- `plot`: title `Tutor Card`, kind pill `Graph`
- `shape`: title `Tutor Card`, kind pill `Sketch`
- `diagram`: title `Tutor Card`, kind pill `Diagram`

Text cards should have a clean explanation-card style, not an equation-card feel. Math inside text still renders through KaTeX.

Tutor cards should keep a stable width by kind. Text cards can use a readable fixed width with responsive clamps, graph and diagram cards can use dimensions suited to their SVG/canvas content. Dragging a card should change only its position, not its measured width.

## Data Model

Frontend workspace state should replace the single handwriting state with a list:

```ts
type StudentCard = {
  id: string;
  label: string;
  position: Point;
  size: Size;
  isCapturing: boolean;
};
```

Workspace actions should include:

- `add_student_card`
- `move_student_card`
- `resize_student_card`
- `set_student_card_capturing`
- existing tutor object actions

The first card can use a stable id like `student-card-1`. New ids should be deterministic within a session, such as `student-card-2`, `student-card-3`.

Backend `UserBoardSnapshot` should add optional card metadata while remaining tolerant of older clients:

```py
card_id: str = "student-card-1"
card_label: str | None = None
```

`BoardState` should track readings by card id. It should expose a combined text view for `WhiteboardAgent` and `read_user_board`, for example:

```text
Student Card 1:
...

Student Card 2:
...
```

Blank snapshots should clear only the matching card's reading, not every card.

Tutor board items should add a new Mermaid-backed diagram variant:

```py
class AiBoardDiagram(BaseModel):
    kind: Literal["diagram"]
    id: str
    syntax: Literal["mermaid"] = "mermaid"
    source: str
    label: str | None = None
```

Mirror this type in `frontend/src/lib/whiteboard.ts` and include it in the `AiBoardItem` union on both sides.

## Placement Design

Introduce a pure placement helper that receives known occupied rectangles and returns a new position for a requested card size. It should scan deterministic candidate positions in world coordinates:

- visible board margin positions first
- then a grid expanding right and down
- avoid overlaps with existing tutor cards and student cards
- avoid currently open overlays when their bounds are known
- fall back to a staggered position if no candidate is free

This helper should be unit-testable without React. It should be used for both new tutor objects and newly added student cards.

Tutor card default placement should preserve existing positions for upserts. Only genuinely new items need placement.

## Agent Diagram Support

Use a hybrid visual model:

- `diagram` for structured Mermaid diagrams: factor trees, flowcharts, step diagrams, boxes/arrows, relationship diagrams, concept maps, and comparison trees.
- `shape` for freeform SVG sketches: number lines, fraction bars, geometric figures, simple area models, and visuals that need precise 2D placement.
- `plot` for function graphs.
- `text` for explanations, formulas, and equations.

Update the OpenAI board extractor prompt with positive `diagram` and `shape` sections:

- If the sentence explicitly asks to draw a factor tree, flowchart, relationship diagram, step diagram, boxes/arrows, or concept map, emit a `diagram` item with Mermaid source.
- Mermaid source must be compact and valid. Prefer `flowchart TD` or `flowchart LR`.
- Mermaid labels should be short math-teaching labels, not full paragraphs.
- If the sentence asks to draw a triangle, number line, fraction bar, area model, or geometric sketch, emit a `shape` item with a simple sanitized SVG fragment without the `<svg>` wrapper.
- Prefer simple SVG primitives: `line`, `path`, `circle`, `rect`, `text`, `polyline`, and `polygon`.
- Include labels only when they are part of the visual.
- Use `diagram` or `shape`, not `text`, for "draw a diagram of..." requests unless the request is impossible to visualize.

Add examples for common math visuals:

- factor tree for prime factorization as Mermaid `flowchart TD`
- boxes/arrows showing a transformation as Mermaid `flowchart LR`
- comparison tree as Mermaid
- number line for divisors or inequalities as SVG `shape`
- fraction bar / partition sketch as SVG `shape`
- triangle or rectangle with labeled sides as SVG `shape`

Keep plot rules separate: function definitions still produce `plot` cards, not Mermaid diagrams or SVG shapes. Plain spoken explanations still produce `text` cards.

## Error Handling

Malformed snapshots without card ids should be treated as `student-card-1`.

If one student card OCR read fails, the backend should leave that card's previous reading untouched and continue processing later snapshots from any card.

If placement cannot find an open slot, the card should still appear using the fallback staggered position. It is better to spawn visibly with some overlap than to drop the card.

If the extractor emits malformed SVG, existing frontend sanitization remains the last line of defense. The prompt should still discourage complex or unsafe SVG.

If Mermaid fails to parse or render, the frontend should show a small invalid-diagram fallback that includes the label when available and does not crash the board.

## Testing

Frontend tests:

- Placement helper chooses an empty slot when existing rectangles occupy the default slot.
- New student card action creates a distinct card id and uses placement.
- Tutor object creation preserves existing positions on upsert.
- Tutor text/graph/sketch/diagram labels map to `Text`, `Graph`, `Sketch`, and `Diagram`.
- Card width rules are stable enough that position changes do not alter the configured width.
- Mermaid diagram cards render valid Mermaid source and show a fallback for invalid source.

Backend tests:

- `UserBoardSnapshot` accepts missing card id as `student-card-1`.
- `AiBoardDiagram` validates and is included in the board item union.
- `BoardState` records, clears, and combines readings per student card.
- Listener blank snapshot clears only the matching card.
- `read_user_board` and `WhiteboardAgent` include combined card-labeled readings.
- Extractor prompt includes Mermaid diagram rules, SVG shape rules, and examples for each.

Verification:

- `cd backend && uv run pytest`
- `cd frontend && npm run test:math`
- `cd frontend && npm run test:canvas`
- new frontend board placement tests
- `cd frontend && npm run lint`
- `cd frontend && npm run build`

## Implementation Notes

Keep the existing `user_board` topic and `ai_board` topic. The protocol change is additive for `user_board`, so old clients remain compatible.

Avoid adding a new state library. The existing reducer pattern is appropriate; extend it rather than introducing global state.

Avoid making the board extractor a general diagram generator. It should produce simple math-teaching diagrams only when the tutor's sentence clearly benefits from a visual object.

Mermaid should be lazy-loaded on the frontend so ordinary sessions that only use text/plot cards do not pay the render cost.

Keep card placement logic outside React components so it can be tested and reused by tutor cards and student cards.
