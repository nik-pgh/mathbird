# Private Board Ink and Sticky Notes Design

## Context

The session board currently gives students a draggable student card with its own drawing toolbar. That student card is the AI-readable surface: its canvas snapshots are sent on the `user_board` LiveKit topic so the tutor can inspect student work.

The requested change keeps that contract. The student card remains the tutor-watched surface. New board-wide sketching and sticky notes are private workspace tools for student ideation and are not read by the AI.

## Goals

- Add a sticky note button below the existing add-student-card button in the top-right board actions.
- Sticky notes are editable, movable, and private. Their text is never included in `user_board` snapshots.
- Add board-wide drawing so the student can sketch on the workspace outside cards.
- Keep the student card as the only AI-readable drawing/text surface.
- Move drawing controls out of the student card into a board-level tool palette.
- Improve handwriting stability and smoothness, and support multiple ink colors.
- Make undo and clear operate on the currently active drawing area:
  - If the most recent stroke was inside a student card, undo/clear affects that card.
  - If the most recent stroke was on the private board canvas, undo/clear affects private board ink.

## Non-Goals

- Do not remove student cards.
- Do not send sticky note content to the AI.
- Do not send private board-wide ink to the AI.
- Do not change backend `user_board` schemas in this phase.
- Do not add persistence across reloads unless the existing session state already preserves it.

## User Model

The student sees one shared board with three kinds of surfaces:

- **Student card:** tutor-watched work area. Drawing here is AI-readable through the existing snapshot path.
- **Private board ink:** freeform scratch work across the board. Drawing here is for organization and ideation only.
- **Sticky notes:** private editable notes. These can hold reminders, labels, or rough thoughts the tutor should not inspect.

The top-right board action area gains a sticky-note button below the add-student-card button. A board-level sketch toolbar appears near the board edge with pen, eraser, undo, clear, and color swatches.

## Interaction Design

### Board-Level Tool Palette

The board-level palette owns the active drawing tool for both student-card ink and private board ink:

- Pen
- Eraser
- Undo
- Clear
- Color swatches

The palette is outside individual student cards, so student cards no longer render their own `Pen`, `Eraser`, `Undo`, or `Clear` controls.

### Student Card Drawing

The student card still contains a canvas, and drawing inside the card still updates the card-local stroke state. Its snapshots continue to include only card content and metadata such as `card_id` and `card_label`.

Because the tools move to the shared palette, the student card receives the active tool, selected color, and drawing commands from the workspace. It reports when a card stroke becomes the most recent active area so undo/clear target the correct card.

### Private Board Drawing

A new private board ink canvas is rendered inside the zoomable `CanvasViewport` world, behind tutor objects, student cards, and sticky notes, but above the board background.

Private board strokes use world coordinates so they remain aligned while panning and zooming. They are not sent over `user_board`.

Drawing on empty board space creates private strokes unless space-pan or another object interaction is active.

### Sticky Notes

Sticky notes are reducer-managed workspace objects with:

- `id`
- `position`
- `size`
- `text`

They support typing, moving, and resizing. Pointer events inside the note text editor do not start dragging. Dragging uses a note header or grip.

Sticky notes are rendered above private board ink and below or alongside cards/tutor objects using the existing object layering conventions.

### Undo and Clear Targeting

The workspace tracks the active ink target:

- `{ kind: "student_card", cardId }`
- `{ kind: "private_board" }`

When a stroke is committed, that surface becomes active.

Undo removes the last stroke from the active target only.

Clear clears all strokes from the active target only.

If no target has strokes, undo and clear are disabled.

## Architecture

### State

`workspaceTypes.ts` gains:

- Sticky note state and actions.
- Private board ink state.
- Board-level ink tool state: tool, color, and active target.

The reducer owns stable, serializable workspace state for sticky notes, private strokes, selected tool, selected color, and active target.

Student-card stroke state may remain local to `HandwritingPanel` for this phase, but the panel must expose imperative-safe callbacks for workspace-level undo/clear. If reducer ownership becomes simpler during implementation, card strokes may be lifted into workspace state as long as the snapshot contract remains unchanged.

### Components

- `BoardInkToolbar`: renders board-level drawing tools and color swatches.
- `PrivateBoardInkLayer`: renders and handles private board strokes in world coordinates.
- `StickyNoteLayer` or `StickyNote`: renders sticky notes and dispatches note edits/moves/resizes.
- `HandwritingPanel`: removes local toolbar UI, consumes active tool/color, and supports workspace-level undo/clear commands.
- `SharedReasoningWorkspace`: wires the board actions, tool palette, private ink layer, sticky notes, and student cards together.

### Drawing Quality

Both student-card and private-board drawing should use the existing `perfect-freehand` dependency for smoother strokes. Improvements should include:

- Pointer capture for the active pointer.
- Coalesced pointer events when available.
- Pressure-aware points with a stable fallback pressure.
- Stroke smoothing settings tuned for handwriting.
- Color stored per stroke.

### AI Boundary

Only the student card snapshot code publishes to `USER_BOARD_TOPIC`.

Private board ink and sticky notes never call `send()` on `user_board`, and they are not drawn into the student card snapshot canvas.

## Error Handling and Edge Cases

- Creating a sticky note places it in open space using the same placement helpers used by cards.
- Empty sticky note text is allowed.
- Undo with no strokes is a no-op.
- Clear with no strokes is a no-op.
- Drawing does not begin when space-pan is active.
- Drawing does not begin from inputs, buttons, sticky-note editors, resize handles, or object drag handles.
- Panning and zooming remain available through existing wheel and space-pan behavior.

## Testing

Extend the existing frontend board script tests to cover:

- Sticky note creation, movement, resize, and text update actions.
- Board ink tool/color actions.
- Active ink target switching between private board and student card.
- Undo/clear target only the active drawing area.
- Source-level guard that sticky notes and private board ink do not use `USER_BOARD_TOPIC` sends.
- Student card source no longer renders local pen/eraser/undo/clear toolbar controls.

Run:

- `cd frontend && npm run test:board`
- `cd frontend && npm run lint`
- `cd frontend && npm run build`

Use browser verification on `/session` to confirm:

- Sticky-note button appears below add-student-card.
- Board-level toolbar renders.
- Student card still renders with topic input and drawing surface, but without local drawing toolbar.
- Sticky notes can be created and edited.
- No Vite error overlay appears.
