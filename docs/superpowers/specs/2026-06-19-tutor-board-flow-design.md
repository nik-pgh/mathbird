# Tutor Board Flow Design

## Goal

Improve the shared reasoning workspace so tutor boards behave like a readable sequence of lesson artifacts instead of a single active card with a small history strip. Students should be able to revisit previous tutor boards, expand them in place, resize tutor boards, and label their own handwriting cards with useful topic names.

## Current State

The frontend already models tutor items as `BoardObject` entries with `position`, optional `size`, and optional `collapsed` state. `TutorObjectLayer` currently chooses one active object and renders all other objects as compact history buttons above it. The reducer collapses prior objects when new AI items arrive, but the UI does not show older boards as full-width ribbons in an ordered flow. Tutor cards are draggable but not resizable.

Student handwriting cards already have a `label` in `StudentCardState`, and `HandwritingPanel` sends that label as `user_board.card_label`. The current label is generated as `Student Card N` and is not editable by the student.

## Tutor Board Behavior

Tutor boards will render as an ordered auto-wrapped flow:

- Boards are ordered by creation/update sequence.
- A newly created tutor board appears after the previous board and is expanded.
- Earlier expanded tutor boards collapse to ribbon height when a new board appears.
- Collapsed boards remain visible as top-ribbon rows, not tiny pill buttons.
- Clicking a collapsed ribbon expands that board in place.
- Expanding a board pushes later boards down in the flow.
- When the current column would exceed the tutor flow's max column height, later boards continue in the next column to the right.
- Reflow must avoid overlap between tutor boards.

This flow should preserve long-session readability. It should not create one endless vertical strip on the board.

The initial layout constants should be explicit and easy to tune:

- Horizontal gap between columns: `24px`.
- Vertical gap between tutor boards: `10px`.
- Collapsed ribbon height: `44px`.
- Default max column height: the visible board height minus top/bottom workspace padding, clamped to a minimum of `520px` so short viewports still produce stable columns.
- Column width: the widest tutor board in that column.

## Tutor Board Titles

Collapsed ribbons need a useful title even though the current `ai_board` wire format does not include one. Titles will be derived in the frontend:

- Use `label` for plot and diagram items when present.
- For text items, derive a short title from the first useful line of markdown.
- For shape items, fall back to a generic sketch title.
- If no useful content exists, use `Tutor Board N`.

This avoids a backend wire-schema change for the first implementation. A future backend-generated topic field can replace the frontend derivation if the tutor agent needs richer semantic titles.

## Tutor Board Resizing

Expanded tutor boards will support a bottom-right resize handle:

- Resize changes the board's stored `size`.
- Resize is clamped to `280px` minimum width, `180px` minimum height, `720px` maximum width, and `520px` maximum height.
- Resizing triggers tutor-flow re-layout so later boards move instead of overlapping.
- Collapsed ribbon height does not depend on the expanded content height.
- Existing board content continues to scroll inside the body when content exceeds the board height.

Dragging a tutor board should move the entire tutor flow group, not detach a single board from the ordered flow. The flow origin can continue to use the current first-card position state, while individual board positions become layout outputs produced by the flow helper.

## Student Card Topic Line

Student handwriting cards will support an editable topic line in the card header:

- The existing generated label remains the default: `Student Card 1`, `Student Card 2`, etc.
- The student can click the topic line and type a custom label, such as `Exercise 4.2: radicals`.
- The edited label is stored in workspace state.
- `HandwritingPanel` continues to publish the label through `user_board.card_label`, so backend board reading and agent context receive the student's topic label with snapshots.
- The field should be compact and fit inside the existing card header. It should not require a separate settings panel.

## State And Data Flow

The change is frontend-scoped:

- Extend `WorkspaceAction` with tutor resize and student label update actions.
- Keep tutor board layout state in the reducer or a focused placement helper so behavior is deterministic and testable without a browser.
- Keep using the existing `AiBoardItem` wire shape.
- Keep using the existing `UserBoardSnapshot.card_label` field.
- Do not add a new data-channel topic.

## Components

Expected files to modify:

- `frontend/src/components/session/workspaceTypes.ts`
  - Add actions for tutor resize and student label updates.
- `frontend/src/components/session/workspaceReducer.ts`
  - Preserve/update tutor sizes, derive layout inputs, update student labels.
- `frontend/src/lib/boardPlacement.ts`
  - Add or extend pure helpers for auto-wrapped tutor flow placement.
- `frontend/src/components/session/TutorObjectLayer.tsx`
  - Render all tutor boards in the flow, collapsed or expanded.
  - Add ribbon click behavior and tutor resize handle.
- `frontend/src/components/session/SharedReasoningWorkspace.tsx`
  - Pass tutor resize and student label handlers.
- `frontend/src/components/session/HandwritingPanel.tsx`
  - Render an editable topic line and publish the current label.
- `frontend/src/styles/session.css`
  - Style tutor flow, collapsed ribbons, resize handle, and editable student topic line.
- `frontend/scripts/test-board-placement.mjs`
  - Add deterministic checks for tutor flow layout, collapse/expand behavior, resize preservation, and student label update behavior.

## Testing

Use the existing frontend validation path:

- `cd frontend && npm run test:board`
- `cd frontend && npm run lint`

Manual browser verification should cover:

- New tutor board collapses previous expanded board.
- Clicking an old ribbon expands it in place.
- Expanded old board pushes later boards without overlap.
- Long sessions wrap into a second column.
- Tutor resize handle changes size and reflows later boards.
- Student topic line can be edited and remains visible in the card header.
- Handwriting snapshots still include the edited `card_label`.

## Out Of Scope

- Backend-generated board titles.
- A new `ai_board` schema field.
- Persistent board history across page reloads.
- Grouping boards into semantic chapters or exercises beyond local title derivation.
- Changing the backend board reader or agent persona.
