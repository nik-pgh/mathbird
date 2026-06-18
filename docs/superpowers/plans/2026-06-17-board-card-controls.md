# Board Card Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multiple OCR-readable student handwriting cards, Mermaid-backed tutor diagrams, better tutor card labeling/placement, and stable tutor-card sizing.

**Architecture:** Keep the existing LiveKit `user_board` and `ai_board` topics, but extend their payloads additively. Backend state becomes card-aware for student OCR readings. Frontend workspace state becomes list-based for student cards and uses a pure placement helper for both tutor and student card spawning.

**Tech Stack:** Python 3.11, Pydantic, pytest, LiveKit Agents, React 18, TypeScript, Vite, KaTeX, DOMPurify, Mermaid.

---

## File Map

- Modify `backend/app/agent/whiteboard/messages.py`: add `AiBoardDiagram`; add `card_id` and `card_label` defaults to `UserBoardSnapshot`.
- Modify `backend/app/agent/whiteboard/state.py`: store readings per student card and expose combined text.
- Modify `backend/app/agent/whiteboard/listener.py`: record or clear only the card from each snapshot.
- Modify `backend/app/agent/whiteboard_agent.py`: inject combined card-labeled readings.
- Modify `backend/app/agent/tools.py`: return combined card-labeled readings from `read_user_board`.
- Modify `backend/app/agent/whiteboard/extractor/openai.py`: include `AiBoardDiagram` in structured response and add Mermaid/SVG diagram prompt rules.
- Modify backend tests under `backend/tests/whiteboard/`.
- Modify `frontend/src/lib/whiteboard.ts`: mirror `AiBoardDiagram` and student snapshot card fields.
- Create `frontend/src/lib/boardPlacement.ts`: pure empty-space placement helper.
- Create `frontend/scripts/test-board-placement.mjs`: placement and card-width behavior tests.
- Modify `frontend/package.json`: add `test:board`.
- Modify `frontend/src/components/whiteboard/BoardItem.tsx`: render Mermaid diagram cards with fallback.
- Modify `frontend/src/components/session/workspaceTypes.ts`: replace single handwriting state with `studentCards`.
- Modify `frontend/src/components/session/workspaceReducer.ts`: add card-aware actions and placement.
- Modify `frontend/src/components/session/SharedReasoningWorkspace.tsx`: render multiple `HandwritingPanel` instances and a top-right add button.
- Modify `frontend/src/components/session/HandwritingPanel.tsx`: accept `cardId`/`label` and publish them in snapshots.
- Modify `frontend/src/components/session/TutorObjectLayer.tsx`: add `diagram` label, change `text` label to `Text`.
- Modify `frontend/src/styles/session.css`: top-right board controls, stable tutor widths, text/graph/sketch/diagram visual styles.

---

### Task 1: Backend Card-Aware User Board State

**Files:**
- Modify: `backend/app/agent/whiteboard/messages.py`
- Modify: `backend/app/agent/whiteboard/state.py`
- Modify: `backend/app/agent/whiteboard/listener.py`
- Modify: `backend/app/agent/whiteboard_agent.py`
- Modify: `backend/app/agent/tools.py`
- Test: `backend/tests/whiteboard/test_messages.py`
- Test: `backend/tests/whiteboard/test_state.py`
- Test: `backend/tests/whiteboard/test_listener.py`
- Test: `backend/tests/whiteboard/test_tools.py`
- Test: `backend/tests/whiteboard/test_whiteboard_agent.py`

- [ ] **Step 1: Write failing message/state tests**

Add to `backend/tests/whiteboard/test_messages.py`:

```python
def test_user_board_snapshot_defaults_to_first_student_card() -> None:
    snap = UserBoardSnapshot(
        png_b64="aGVsbG8=",
        captured_at_ms=1700000000123,
        is_empty=False,
    )

    assert snap.card_id == "student-card-1"
    assert snap.card_label is None
```

Add to `backend/tests/whiteboard/test_state.py`:

```python
def test_records_readings_per_student_card() -> None:
    state = BoardState()

    state.record_reading("x = 2", card_id="student-card-1", card_label="Student Card 1")
    state.record_reading("factor tree", card_id="student-card-2", card_label="Student Card 2")

    assert state.is_blank is False
    assert state.user_text == "Student Card 1:\nx = 2\n\nStudent Card 2:\nfactor tree"


def test_record_empty_clears_only_matching_student_card() -> None:
    state = BoardState()
    state.record_reading("x = 2", card_id="student-card-1", card_label="Student Card 1")
    state.record_reading("factor tree", card_id="student-card-2", card_label="Student Card 2")

    state.record_empty(card_id="student-card-1")

    assert state.user_text == "Student Card 2:\nfactor tree"
    assert state.is_blank is False
```

Add to `backend/tests/whiteboard/test_listener.py`:

```python
def _snapshot(
    payload: bytes = b"png-bytes-here",
    *,
    is_empty: bool = False,
    card_id: str = "student-card-1",
    card_label: str | None = None,
) -> bytes:
    snap = UserBoardSnapshot(
        png_b64=base64.b64encode(payload).decode("ascii"),
        captured_at_ms=1700000000000,
        is_empty=is_empty,
        card_id=card_id,
        card_label=card_label,
    )
    return snap.model_dump_json().encode("utf-8")
```

Then add:

```python
async def test_listener_records_snapshot_under_card_id() -> None:
    room = _FakeRoom()
    state = BoardState()
    reader = _RecordingReader("drawn work")

    handle = install_user_board_listener(room=room, state=state, reader=reader, interval=0.05)
    try:
        room.emit(
            "data_received",
            _FakeDataPacket(
                data=_snapshot(card_id="student-card-2", card_label="Student Card 2"),
                topic=USER_BOARD_TOPIC,
            ),
        )
        await asyncio.sleep(0.15)

        assert state.user_text == "Student Card 2:\ndrawn work"
    finally:
        await handle.aclose()


async def test_listener_empty_snapshot_clears_only_matching_card() -> None:
    room = _FakeRoom()
    state = BoardState()
    state.record_reading("left", card_id="student-card-1", card_label="Student Card 1")
    state.record_reading("right", card_id="student-card-2", card_label="Student Card 2")
    reader = _RecordingReader("should not be called")

    handle = install_user_board_listener(room=room, state=state, reader=reader, interval=0.05)
    try:
        room.emit(
            "data_received",
            _FakeDataPacket(
                data=_snapshot(is_empty=True, card_id="student-card-1"),
                topic=USER_BOARD_TOPIC,
            ),
        )
        await asyncio.sleep(0.15)

        assert reader.calls == []
        assert state.user_text == "Student Card 2:\nright"
    finally:
        await handle.aclose()
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd backend && uv run pytest tests/whiteboard/test_messages.py tests/whiteboard/test_state.py tests/whiteboard/test_listener.py -q
```

Expected: FAIL because `UserBoardSnapshot.card_id` and card-aware `BoardState.record_reading(..., card_id=...)` do not exist yet.

- [ ] **Step 3: Implement backend card-aware state**

In `backend/app/agent/whiteboard/messages.py`, change `UserBoardSnapshot` to:

```python
class UserBoardSnapshot(BaseModel):
    """Clients -> server snapshot on the ``user_board`` topic."""

    png_b64: str = Field(description="Base64 PNG, ≤512px on the long edge.")
    captured_at_ms: int = Field(description="Client clock at capture time.")
    is_empty: bool = Field(default=False, description="True iff this card has been cleared.")
    card_id: str = Field(default="student-card-1", description="Stable student card id.")
    card_label: str | None = Field(default=None, description="Human-readable student card label.")
```

Replace `BoardState` in `backend/app/agent/whiteboard/state.py` with a card-aware implementation that keeps compatibility with `.user_text`, `.is_blank`, `.refreshed_at`, and `.age_seconds()`:

```python
@dataclass
class BoardReading:
    card_id: str
    label: str
    text: str
    refreshed_at: float


@dataclass
class BoardState:
    readings: dict[str, BoardReading] = field(default_factory=dict)
    refreshed_at: float | None = None

    @property
    def user_text(self) -> str:
        parts = [
            f"{reading.label}:\n{reading.text.strip()}"
            for reading in sorted(self.readings.values(), key=lambda r: r.label)
            if reading.text.strip()
        ]
        return "\n\n".join(parts)

    @property
    def is_blank(self) -> bool:
        return not self.user_text.strip()

    def record_reading(
        self,
        text: str,
        *,
        card_id: str = "student-card-1",
        card_label: str | None = None,
    ) -> None:
        now = time.time()
        label = card_label or _default_card_label(card_id)
        if text.strip():
            self.readings[card_id] = BoardReading(card_id=card_id, label=label, text=text, refreshed_at=now)
        else:
            self.readings.pop(card_id, None)
        self.refreshed_at = now

    def record_empty(self, *, card_id: str = "student-card-1") -> None:
        self.readings.pop(card_id, None)
        self.refreshed_at = time.time()

    def age_seconds(self) -> float | None:
        if self.refreshed_at is None:
            return None
        return max(0.0, time.time() - self.refreshed_at)


def _default_card_label(card_id: str) -> str:
    suffix = card_id.removeprefix("student-card-")
    return f"Student Card {suffix}" if suffix and suffix != card_id else "Student Card"
```

In `backend/app/agent/whiteboard/listener.py`, change the empty and reading branches:

```python
if snap.is_empty:
    state.record_empty(card_id=snap.card_id)
    continue
...
if text.strip():
    state.record_reading(text, card_id=snap.card_id, card_label=snap.card_label)
else:
    state.record_empty(card_id=snap.card_id)
```

Keep `whiteboard_agent.py` and `tools.py` using `state.user_text`; the property now returns combined card-labeled text.

- [ ] **Step 4: Run backend focused tests**

Run:

```bash
cd backend && uv run pytest tests/whiteboard/test_messages.py tests/whiteboard/test_state.py tests/whiteboard/test_listener.py tests/whiteboard/test_tools.py tests/whiteboard/test_whiteboard_agent.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add backend/app/agent/whiteboard/messages.py backend/app/agent/whiteboard/state.py backend/app/agent/whiteboard/listener.py backend/tests/whiteboard/test_messages.py backend/tests/whiteboard/test_state.py backend/tests/whiteboard/test_listener.py
git commit -m "feat: track student board readings by card"
```

---

### Task 2: Backend Mermaid Diagram Item And Extractor Rules

**Files:**
- Modify: `backend/app/agent/whiteboard/messages.py`
- Modify: `backend/app/agent/whiteboard/__init__.py`
- Modify: `backend/app/agent/whiteboard/extractor/openai.py`
- Test: `backend/tests/whiteboard/test_messages.py`
- Test: `backend/tests/whiteboard/test_extractor_openai.py`

- [ ] **Step 1: Write failing diagram tests**

Add to imports in `backend/tests/whiteboard/test_messages.py`:

```python
AiBoardDiagram,
```

Add to `test_ai_board_update_round_trips_mixed_items()` items:

```python
AiBoardDiagram(
    kind="diagram",
    id="d1",
    syntax="mermaid",
    source="flowchart TD\n  A[42] --> B[2]\n  A --> C[21]",
    label="Factor tree",
),
```

Add assertions:

```python
assert len(restored.items) == 4
assert restored.items[3].kind == "diagram"
```

Add to `backend/tests/whiteboard/test_extractor_openai.py`:

```python
from app.agent.whiteboard.messages import AiBoardDiagram, AiBoardPlot, AiBoardText
```

Add tests:

```python
async def test_extract_diagram_kind() -> None:
    expected = ExtractorResponse(
        items=[
            AiBoardDiagram(
                kind="diagram",
                id="d1",
                syntax="mermaid",
                source="flowchart TD\n  A[42] --> B[2]\n  A --> C[21]",
                label="Factor tree",
            )
        ]
    )
    ex = _make_extractor(expected)

    items = await ex.extract(
        sentence="Draw a factor tree for 42.",
        current_items=[],
        last_sentence=None,
    )

    assert isinstance(items[0], AiBoardDiagram)
    assert items[0].syntax == "mermaid"


async def test_extractor_prompt_contains_mermaid_and_shape_rules() -> None:
    ex = _make_extractor(ExtractorResponse(items=[]))

    await ex.extract(
        sentence="Draw a factor tree for 42.",
        current_items=[],
        last_sentence=None,
    )

    system = ex._client.beta.chat.completions.calls[0]["messages"][0]["content"]
    assert "Mermaid" in system
    assert "flowchart TD" in system
    assert "number line" in system
    assert "shape" in system
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd backend && uv run pytest tests/whiteboard/test_messages.py tests/whiteboard/test_extractor_openai.py -q
```

Expected: FAIL because `AiBoardDiagram` is not defined and extractor prompt lacks Mermaid rules.

- [ ] **Step 3: Implement diagram schema and prompt rules**

In `backend/app/agent/whiteboard/messages.py`, add:

```python
class AiBoardDiagram(BaseModel):
    """A structured diagram rendered from Mermaid source on the client."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["diagram"]
    id: str
    syntax: Literal["mermaid"] = "mermaid"
    source: str = Field(description="Compact Mermaid source, usually flowchart TD or flowchart LR.")
    label: str | None = None
```

Change the union:

```python
AiBoardItem = Annotated[
    AiBoardText | AiBoardPlot | AiBoardShape | AiBoardDiagram,
    Field(discriminator="kind"),
]
```

Export `AiBoardDiagram` from `backend/app/agent/whiteboard/__init__.py`.

In `backend/app/agent/whiteboard/extractor/openai.py`, import `AiBoardDiagram` and change:

```python
_ExtractorItem = AiBoardText | AiBoardPlot | AiBoardShape | AiBoardDiagram
```

Add a positive `diagram` section to `_SYSTEM_PROMPT` before the existing negative rules:

```text
- diagram: a structured visual relationship that Mermaid can express well:
  factor trees, flowcharts, step diagrams, boxes/arrows, relationship diagrams,
  concept maps, and comparison trees. Use Mermaid source with syntax="mermaid".
  Prefer "flowchart TD" or "flowchart LR". Labels must be short.
    Example sentence: "draw a factor tree for 42"
    → {"kind": "diagram", "id": "d1", "syntax": "mermaid", "source": "flowchart TD\n  n42[42] --> n2[2]\n  n42 --> n21[21]\n  n21 --> n3[3]\n  n21 --> n7[7]", "label": "Factor tree for 42"}

- shape: a freeform SVG sketch for geometry, number lines, fraction bars,
  area models, and visuals that need precise 2-D placement. Use simple SVG
  primitives only and omit the outer <svg> wrapper.
    Example sentence: "draw a number line from 0 to 6"
    → {"kind": "shape", "id": "s1", "svg": "<line x1='20' y1='100' x2='180' y2='100' stroke='currentColor'/><text x='18' y='120'>0</text><text x='172' y='120'>6</text>"}
```

Update the id policy sequence:

```text
  shape items: s1, s2, s3, ...
  diagram items: d1, d2, d3, ...
```

- [ ] **Step 4: Run backend extractor tests**

Run:

```bash
cd backend && uv run pytest tests/whiteboard/test_messages.py tests/whiteboard/test_extractor_openai.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add backend/app/agent/whiteboard/messages.py backend/app/agent/whiteboard/__init__.py backend/app/agent/whiteboard/extractor/openai.py backend/tests/whiteboard/test_messages.py backend/tests/whiteboard/test_extractor_openai.py
git commit -m "feat: add mermaid tutor diagram items"
```

---

### Task 3: Frontend Board Types And Placement Helper

**Files:**
- Modify: `frontend/src/lib/whiteboard.ts`
- Create: `frontend/src/lib/boardPlacement.ts`
- Create: `frontend/scripts/test-board-placement.mjs`
- Modify: `frontend/package.json`
- Modify: `frontend/src/components/session/workspaceTypes.ts`
- Modify: `frontend/src/components/session/workspaceReducer.ts`

- [ ] **Step 1: Write failing placement tests**

Create `frontend/scripts/test-board-placement.mjs`:

```js
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import ts from "typescript";

const sourcePath = new URL("../src/lib/boardPlacement.ts", import.meta.url);
const source = fs.readFileSync(sourcePath, "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020,
    esModuleInterop: true,
  },
}).outputText;

const sandbox = { exports: {} };
vm.runInNewContext(compiled, sandbox, { filename: "boardPlacement.ts" });

const { findOpenBoardPosition, rectsOverlap, tutorCardSizeForKind } = sandbox.exports;

assert.equal(rectsOverlap({ x: 0, y: 0, width: 100, height: 100 }, { x: 99, y: 0, width: 100, height: 100 }), true);
assert.equal(rectsOverlap({ x: 0, y: 0, width: 100, height: 100 }, { x: 120, y: 0, width: 100, height: 100 }), false);

const first = findOpenBoardPosition({
  size: { width: 320, height: 180 },
  occupied: [],
  viewport: { x: 0, y: 0, width: 900, height: 600 },
});
assert.deepEqual(first, { x: 36, y: 36 });

const second = findOpenBoardPosition({
  size: { width: 320, height: 180 },
  occupied: [{ x: 36, y: 36, width: 320, height: 180 }],
  viewport: { x: 0, y: 0, width: 900, height: 600 },
});
assert.notDeepEqual(second, { x: 36, y: 36 });

assert.deepEqual(tutorCardSizeForKind("text"), { width: 340, height: 180 });
assert.deepEqual(tutorCardSizeForKind("plot"), { width: 360, height: 250 });
assert.deepEqual(tutorCardSizeForKind("shape"), { width: 340, height: 240 });
assert.deepEqual(tutorCardSizeForKind("diagram"), { width: 380, height: 260 });
```

Add to `frontend/package.json` scripts:

```json
"test:board": "node scripts/test-board-placement.mjs"
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
cd frontend && npm run test:board
```

Expected: FAIL because `frontend/src/lib/boardPlacement.ts` does not exist.

- [ ] **Step 3: Implement placement helper and TS types**

Create `frontend/src/lib/boardPlacement.ts`:

```ts
export interface BoardRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface BoardSize {
  width: number;
  height: number;
}

export type VisualKind = "text" | "plot" | "shape" | "diagram";

export function rectsOverlap(a: BoardRect, b: BoardRect, gap = 14): boolean {
  return !(
    a.x + a.width + gap <= b.x
    || b.x + b.width + gap <= a.x
    || a.y + a.height + gap <= b.y
    || b.y + b.height + gap <= a.y
  );
}

export function tutorCardSizeForKind(kind: VisualKind): BoardSize {
  if (kind === "plot") return { width: 360, height: 250 };
  if (kind === "shape") return { width: 340, height: 240 };
  if (kind === "diagram") return { width: 380, height: 260 };
  return { width: 340, height: 180 };
}

export function findOpenBoardPosition({
  size,
  occupied,
  viewport,
  margin = 36,
}: {
  size: BoardSize;
  occupied: BoardRect[];
  viewport: BoardRect;
  margin?: number;
}): { x: number; y: number } {
  const stepX = size.width + 28;
  const stepY = size.height + 28;
  const maxX = Math.max(viewport.x + margin, viewport.x + viewport.width - size.width - margin);
  const maxY = Math.max(viewport.y + margin, viewport.y + viewport.height - size.height - margin);

  for (let y = viewport.y + margin; y <= maxY; y += stepY) {
    for (let x = viewport.x + margin; x <= maxX; x += stepX) {
      const candidate = { x, y, width: size.width, height: size.height };
      if (!occupied.some((rect) => rectsOverlap(candidate, rect))) {
        return { x, y };
      }
    }
  }

  const offset = occupied.length * 28;
  return { x: viewport.x + margin + offset, y: viewport.y + margin + offset };
}
```

In `frontend/src/lib/whiteboard.ts`, add:

```ts
export interface AiBoardDiagram {
  kind: "diagram";
  id: string;
  syntax: "mermaid";
  source: string;
  label?: string | null;
}

export type AiBoardItem = AiBoardText | AiBoardPlot | AiBoardShape | AiBoardDiagram;
```

Add to `UserBoardSnapshot`:

```ts
card_id?: string;
card_label?: string | null;
```

In `frontend/src/components/session/workspaceTypes.ts`, add:

```ts
export interface StudentCardState {
  id: string;
  label: string;
  position: Point;
  size: Size;
  isCapturing: boolean;
}
```

Change `WorkspaceState` to use:

```ts
studentCards: StudentCardState[];
```

Change actions to include:

```ts
| { type: "add_student_card"; boardSize: Size }
| { type: "move_student_card"; id: string; position: Point }
| { type: "resize_student_card"; id: string; size: Size }
| { type: "set_student_card_capturing"; id: string; value: boolean };
```

In `workspaceReducer.ts`, initialize `studentCards` with the previous default handwriting panel values using id `student-card-1` and label `Student Card 1`. Add reducer branches for the new actions and compute new-card placement through `findOpenBoardPosition`.

- [ ] **Step 4: Run placement test and typecheck**

Run:

```bash
cd frontend && npm run test:board && npm run lint
```

Expected: `test:board` PASS; `lint` may fail until Task 5 updates components to the new `studentCards` state shape. If lint fails only because components still reference `state.handwriting`, continue to Task 5 before committing.

---

### Task 4: Frontend Mermaid Diagram Rendering

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/src/components/whiteboard/BoardItem.tsx`
- Modify: `frontend/src/styles/session.css`

- [ ] **Step 1: Add Mermaid dependency**

Run:

```bash
cd frontend && npm install mermaid
```

Expected: `package.json` and `package-lock.json` update with Mermaid.

- [ ] **Step 2: Implement diagram renderer**

In `frontend/src/components/whiteboard/BoardItem.tsx`, import `useEffect` and `useState`, add `AiBoardDiagram` to type imports, and route diagram items:

```tsx
if (item.kind === "diagram") return <DiagramItem item={item} />;
```

Add:

```tsx
function DiagramItem({ item }: { item: AiBoardDiagram }) {
  const [html, setHtml] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setHtml(null);
    setFailed(false);

    void import("mermaid")
      .then(async ({ default: mermaid }) => {
        mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: "neutral" });
        const result = await mermaid.render(`diagram-${item.id}`, item.source);
        if (!cancelled) setHtml(result.svg);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });

    return () => {
      cancelled = true;
    };
  }, [item.id, item.source]);

  if (failed) {
    return (
      <div className="ai-card board-item-diagram invalid">
        {item.label ?? "Invalid diagram"}
      </div>
    );
  }

  return (
    <div className="ai-card board-item-diagram">
      {item.label ? <div className="board-item-diagram-label">{item.label}</div> : null}
      {html ? (
        <div
          className="board-item-diagram-svg"
          dangerouslySetInnerHTML={{
            __html: DOMPurify.sanitize(html, { USE_PROFILES: { svg: true, svgFilters: true } }),
          }}
        />
      ) : (
        <div className="board-item-diagram-loading">Rendering diagram</div>
      )}
    </div>
  );
}
```

Add CSS for `.board-item-diagram`, `.board-item-diagram-label`, `.board-item-diagram-svg`, and `.board-item-diagram-loading` in `frontend/src/styles/session.css`.

- [ ] **Step 3: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS. Vite may print the existing chunk-size warning.

- [ ] **Step 4: Commit Tasks 3 and 4 together if lint was blocked**

If Task 3 could not commit due to transitional type errors, wait until Task 5 completes and commit Tasks 3-5 together. If Task 3 was already committed, commit Task 4:

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/components/whiteboard/BoardItem.tsx frontend/src/styles/session.css frontend/src/lib/whiteboard.ts
git commit -m "feat: render mermaid tutor diagrams"
```

---

### Task 5: Multiple Student Cards And Board Control

**Files:**
- Modify: `frontend/src/components/session/SharedReasoningWorkspace.tsx`
- Modify: `frontend/src/components/session/HandwritingPanel.tsx`
- Modify: `frontend/src/components/session/workspaceReducer.ts`
- Modify: `frontend/src/components/session/workspaceTypes.ts`
- Modify: `frontend/src/styles/session.css`

- [ ] **Step 1: Update HandwritingPanel props and snapshots**

In `frontend/src/components/session/HandwritingPanel.tsx`, change props:

```ts
interface Props {
  cardId: string;
  label: string;
  position: { x: number; y: number };
  size: { width: number; height: number };
  isCapturing: boolean;
  onMove: (position: { x: number; y: number }) => void;
  onResize: (size: { width: number; height: number }) => void;
  onCaptureStateChange: (value: boolean) => void;
}
```

Render `{label}` in the drag handle instead of the fixed text.

In both snapshot sends, include:

```ts
card_id: cardId,
card_label: label,
```

- [ ] **Step 2: Render add button and multiple panels**

In `SharedReasoningWorkspace.tsx`, add `boardSizeRef` state or derive from `board.getBoundingClientRect()` when clicked:

```tsx
const addStudentCard = useCallback(() => {
  const board = boardRef.current;
  const rect = board?.getBoundingClientRect();
  dispatch({
    type: "add_student_card",
    boardSize: {
      width: rect?.width ?? 900,
      height: rect?.height ?? 600,
    },
  });
}, []);
```

Inside `.shared-board`, render before overlays:

```tsx
<div className="board-top-actions">
  <button type="button" onClick={addStudentCard}>
    Student Card
  </button>
</div>
```

Replace the single `HandwritingPanel` with:

```tsx
{state.studentCards.map((card) => (
  <HandwritingPanel
    key={card.id}
    cardId={card.id}
    label={card.label}
    position={card.position}
    size={card.size}
    isCapturing={card.isCapturing}
    onMove={(position) => dispatch({ type: "move_student_card", id: card.id, position })}
    onResize={(size) => dispatch({ type: "resize_student_card", id: card.id, size })}
    onCaptureStateChange={(value) =>
      dispatch({ type: "set_student_card_capturing", id: card.id, value })
    }
  />
))}
```

Update `defaultHandwritingLayout` usage so responsive default applies to `student-card-1` only when it has not been customized.

- [ ] **Step 3: Add board top action styles**

In `frontend/src/styles/session.css`, add:

```css
.board-top-actions {
  position: absolute;
  top: 14px;
  right: 14px;
  z-index: 6;
  display: flex;
  gap: 8px;
}

.board-top-actions button {
  min-height: 36px;
  padding: 0 12px;
  border: 1px solid rgba(41, 72, 62, 0.22);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.86);
  color: var(--mb-green);
  font-size: 12px;
  font-weight: 750;
  box-shadow: 0 6px 18px rgba(32, 54, 47, 0.1);
  backdrop-filter: blur(8px);
}

.board-top-actions button:hover {
  border-color: var(--mb-green);
  background: #ffffff;
}
```

- [ ] **Step 4: Run frontend checks**

Run:

```bash
cd frontend && npm run test:board && npm run test:math && npm run test:canvas && npm run lint
```

Expected: PASS.

- [ ] **Step 5: Commit Task 5**

```bash
git add frontend/src/components/session/SharedReasoningWorkspace.tsx frontend/src/components/session/HandwritingPanel.tsx frontend/src/components/session/workspaceReducer.ts frontend/src/components/session/workspaceTypes.ts frontend/src/styles/session.css frontend/src/lib/boardPlacement.ts frontend/scripts/test-board-placement.mjs frontend/package.json frontend/src/lib/whiteboard.ts
git commit -m "feat: add multiple student handwriting cards"
```

---

### Task 6: Tutor Card Labels, Stable Widths, And Empty-Space Placement

**Files:**
- Modify: `frontend/src/components/session/TutorObjectLayer.tsx`
- Modify: `frontend/src/components/session/workspaceReducer.ts`
- Modify: `frontend/src/styles/session.css`
- Test: `frontend/scripts/test-board-placement.mjs`

- [ ] **Step 1: Update card labels**

In `TutorObjectLayer.tsx`, change labels:

```ts
const KIND_LABELS: Record<BoardObject["kind"], string> = {
  text: "Text",
  plot: "Graph",
  shape: "Sketch",
  diagram: "Diagram",
};
```

Keep title `Tutor Card`.

- [ ] **Step 2: Use placement helper for new tutor objects**

In `workspaceReducer.ts`, use `tutorCardSizeForKind(item.kind)` when creating board objects, and pass occupied rectangles from existing tutor objects and student cards into `findOpenBoardPosition`. Preserve `existing.position` and `existing.size` on upsert.

The new object should store:

```ts
size: existing?.size ?? tutorCardSizeForKind(item.kind)
```

- [ ] **Step 3: Apply stable dimensions**

In `TutorObjectLayer.tsx`, set width and minHeight from object size:

```tsx
style={{
  left: object.position.x,
  top: object.position.y,
  width: object.size?.width,
  minHeight: object.size?.height,
}}
```

In `session.css`, replace tutor sizing rules:

```css
.tutor-object {
  position: absolute;
  width: 340px;
  min-width: 0;
  max-width: none;
  ...
}

.tutor-object-text .ai-card {
  min-height: 130px;
}

.tutor-object-plot .ai-card,
.tutor-object-shape .ai-card,
.tutor-object-diagram .ai-card {
  min-height: 190px;
}
```

- [ ] **Step 4: Extend placement test**

Add to `frontend/scripts/test-board-placement.mjs`:

```js
const fallback = findOpenBoardPosition({
  size: { width: 320, height: 180 },
  occupied: Array.from({ length: 20 }, (_, i) => ({
    x: 36 + (i % 4) * 348,
    y: 36 + Math.floor(i / 4) * 208,
    width: 320,
    height: 180,
  })),
  viewport: { x: 0, y: 0, width: 360, height: 260 },
});
assert.equal(typeof fallback.x, "number");
assert.equal(typeof fallback.y, "number");
```

- [ ] **Step 5: Run frontend checks**

Run:

```bash
cd frontend && npm run test:board && npm run lint && npm run build
```

Expected: PASS. Vite may print the existing chunk-size warning.

- [ ] **Step 6: Commit Task 6**

```bash
git add frontend/src/components/session/TutorObjectLayer.tsx frontend/src/components/session/workspaceReducer.ts frontend/src/styles/session.css frontend/scripts/test-board-placement.mjs
git commit -m "fix: place tutor cards in open board space"
```

---

### Task 7: Full Verification

**Files:**
- No source edits expected.

- [ ] **Step 1: Run backend full suite**

```bash
cd backend && uv run pytest
```

Expected: all tests pass.

- [ ] **Step 2: Run frontend focused tests**

```bash
cd frontend && npm run test:math && npm run test:canvas && npm run test:board
```

Expected: all focused tests pass.

- [ ] **Step 3: Run frontend typecheck and build**

```bash
cd frontend && npm run lint && npm run build
```

Expected: typecheck and build pass. The known Vite chunk-size warning is acceptable.

- [ ] **Step 4: Manual local checks**

Start or reuse the frontend dev server:

```bash
cd frontend && npm run dev
```

Open `/session` with the backend/LiveKit setup available and verify:

- Clicking `Student Card` creates `Student Card 2`.
- Drawing on separate student cards sends snapshots with distinct `card_id` values.
- Tutor context shows combined card-labeled OCR readings in backend logs/tests.
- Asking "draw a factor tree for 42" produces a Mermaid diagram card when the extractor is enabled.
- Asking "draw a number line" produces an SVG sketch card when the extractor is enabled.
- Asking "graph y = x squared" produces a graph card.
- Plain explanation appears as a Text tutor card.
- New tutor cards avoid occupied student/tutor card space when possible.
- Dragging a tutor card far right does not change its width.

- [ ] **Step 5: Final status**

If verification passes, report the latest commit hash and the commands run. If manual LiveKit verification is not possible in the current environment, report that limitation explicitly.
