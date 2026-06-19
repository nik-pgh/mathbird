# Cool Mist Grey Palette Design

## Goal

Cool down Mathbird's visual tone without changing layout, behavior, or the current accent roles. The current app feels too warm because the core surfaces use cream, ivory, beige borders, and warm paper gradients. The target direction is a cool neutral white and mist-grey surface system with recognizable green, yellow, coral/orange, and purple accents.

## Approved Direction

Use the "Mist Grey" direction selected during visual review:

- App background: cool near-white, about `#f7fafb`.
- Board and soft surfaces: subtle mist-grey whites, about `#f5f8fa` and `#edf3f5`.
- Borders: cool grey-blue, about `#d2dde2`.
- Primary green accent: keep the existing green role, but shift it cooler and a little brighter, about `#2b6258`.
- Sticky-note yellow, danger/capture coral, and tutor-object purple remain visible and familiar. Their supporting soft colors are cooled only where they currently rely on warm cream.

## Scope

Update the frontend palette only.

Primary files:

- `frontend/src/styles/global.css`
- `frontend/src/styles/session.css`
- `frontend/src/components/session/HandwritingPanel.tsx`
- `frontend/src/components/session/workspaceReducer.ts`
- `frontend/src/components/session/workspaceTypes.ts`
- `frontend/src/components/session/BoardInkToolbar.tsx`

Expected changes:

- Replace app-wide cream tokens such as `--mb-paper`, `--bg`, `--bg-soft`, `--bg-pad`, `--border`, and `--border-strong` with Mist Grey values.
- Update `--mb-green` and `--mb-green-soft` to the cooler green family.
- Keep `--mb-coral` and `--mb-lavender` roles, and cool their soft background tokens only enough to remove warm cream casts.
- Replace hard-coded warm board, handwriting, sticky-note, and alert colors that bypass global tokens.
- Update handwriting canvas defaults and ink color type defaults only where they encode the old warm palette.

## Non-Goals

- No layout redesign.
- No component restructuring.
- No backend changes.
- No new theme-switching feature.
- No removal of yellow, coral/orange, or purple accents.
- No broad restyling of the evaluation dashboard beyond avoiding obvious clashes caused by shared global tokens.

## Verification

Run:

- `cd frontend && npm run lint`
- `cd frontend && npm run build`

Then start the frontend dev server and visually inspect:

- Library/upload route `/`
- Session route `/session`
- Handwriting panel, sticky notes, tutor objects, transcript overlay, voice composer, and top controls

Success criteria:

- The app no longer reads as cream/beige/warm overall.
- Surfaces read as cool neutral white or light mist grey, not saturated blue.
- Green, yellow, coral/orange, and purple accent roles are still clear.
- Text contrast remains readable.
- No visible overlap, layout shift, or broken controls are introduced.
