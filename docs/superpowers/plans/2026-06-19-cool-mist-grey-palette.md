# Cool Mist Grey Palette Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Mathbird's warm cream/beige visual tone with the approved Mist Grey cool-neutral palette while preserving the green, yellow, coral/orange, and purple accent roles.

**Architecture:** The frontend already centralizes most palette values in `frontend/src/styles/global.css`, so the implementation starts with tokens and then patches hard-coded session colors that bypass tokens. No layout, state flow, API, or backend behavior changes.

**Tech Stack:** Vite, React 18, TypeScript, plain CSS, lucide-react icons.

---

## File Structure

- Modify `frontend/src/styles/global.css`: source of global color tokens for app surfaces, borders, text, and primary accents.
- Modify `frontend/src/styles/session.css`: session workspace-specific gradients, sticky notes, handwriting panel, tutor objects, transcript/voice chrome, and error/capture colors.
- Modify `frontend/src/components/session/HandwritingPanel.tsx`: canvas snapshot fill color currently hard-codes the old warm paper background.
- Modify `frontend/src/components/session/workspaceTypes.ts`: ink color union currently includes the old dark green ink.
- Modify `frontend/src/components/session/workspaceReducer.ts`: default ink color currently uses the old dark green ink.
- Modify `frontend/src/components/session/BoardInkToolbar.tsx`: visible ink swatches currently include the old dark green ink.

## Task 1: Update Global Palette Tokens

**Files:**
- Modify: `frontend/src/styles/global.css`

- [ ] **Step 1: Replace the `:root` color tokens**

In `frontend/src/styles/global.css`, replace only the color-token values at the top of the file with this Mist Grey palette:

```css
:root {
  --mb-green: #2b6258;
  --mb-green-soft: #dcece8;
  --mb-coral: #ff775f;
  --mb-coral-soft: #ffe0da;
  --mb-lavender: #c184d8;
  --mb-lavender-soft: #f0dcf7;
  --mb-paper: #f5f8fa;
  --mb-paper-deep: #e3edf1;
  --mb-ink: #1f3934;

  --bg: #f7fafb;
  --bg-soft: #edf3f5;
  --bg-pad: #f5f8fa;

  --border: #d2dde2;
  --border-strong: #b8c8d0;

  --text: var(--mb-ink);
  --text-2: #60716d;
  --text-3: #879895;
```

Keep the existing radius, shadow, and font tokens after `--accent-danger`.

- [ ] **Step 2: Update primary button hover to stay in the green family**

In `frontend/src/styles/global.css`, change the primary topbar button hover from the neutral black hover to the cooler green:

```css
.topbar .btn.primary:hover {
  background: var(--mb-green);
}
```

- [ ] **Step 3: Run frontend typecheck after token edits**

Run:

```bash
cd frontend && npm run lint
```

Expected: `tsc -b --noEmit` completes with exit code 0.

- [ ] **Step 4: Commit token changes**

Run:

```bash
git add frontend/src/styles/global.css
git commit -m "style: cool global palette tokens"
```

## Task 2: Cool Session Workspace Hard-Coded Colors

**Files:**
- Modify: `frontend/src/styles/session.css`

- [ ] **Step 1: Update workspace and board surfaces**

In `frontend/src/styles/session.css`, change the opening comment and surface colors:

```css
/*
 * Loaded by SessionPage.tsx. The session is now a spatial shared workspace:
 * a cool board with movable learning surfaces and a persistent voice composer.
 */

.shared-workspace {
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  height: calc(100vh - 56px);
  min-height: 0;
  background: var(--bg-pad);
}

.shared-board {
  position: relative;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  touch-action: none;
  background: linear-gradient(135deg, var(--mb-paper) 0%, var(--bg) 55%, var(--bg-soft) 100%);
}
```

- [ ] **Step 2: Update sticky note colors without removing the yellow role**

Replace the `.sticky-note`, `.sticky-note-handle`, `.sticky-note-text::placeholder`, and `.sticky-note-resize` warm yellow/brown values with:

```css
.sticky-note {
  border: 1px solid rgba(130, 132, 46, 0.28);
  background: #f7f2a5;
  box-shadow:
    0 8px 0 rgba(130, 132, 46, 0.16),
    0 14px 26px rgba(26, 43, 52, 0.14);
  color: #3a3b18;
}

.sticky-note-handle {
  border-bottom: 1px solid rgba(130, 132, 46, 0.16);
  background: rgba(237, 232, 126, 0.52);
  color: rgba(58, 59, 24, 0.72);
}

.sticky-note-text::placeholder {
  color: rgba(58, 59, 24, 0.5);
}

.sticky-note-resize {
  background:
    linear-gradient(135deg, transparent 50%, rgba(130, 132, 46, 0.42) 50%);
}
```

Keep the existing layout declarations in each rule.

- [ ] **Step 3: Update handwriting panel and surface colors**

Replace warm handwriting panel colors with cool neutral surfaces:

```css
.handwriting-panel {
  background: #ffffff;
  box-shadow:
    0 8px 0 var(--mb-green),
    0 14px 34px rgba(26, 43, 52, 0.16);
}

.handwriting-panel-head {
  background: rgba(255, 255, 255, 0.9);
}

.handwriting-topic-input:focus {
  background: rgba(255, 255, 255, 0.9);
}

.handwriting-surface {
  background:
    radial-gradient(circle, rgba(43, 98, 88, 0.13) 1px, transparent 1px),
    linear-gradient(180deg, #ffffff, var(--bg-pad));
  background-size:
    16px 16px,
    auto;
}
```

Keep the existing border, sizing, and interaction declarations.

- [ ] **Step 4: Update tutor object purple support colors**

Replace hard-coded old lavender support colors with the approved cooler purple family:

```css
.tutor-object {
  border: 1px solid rgba(193, 132, 216, 0.55);
  box-shadow:
    0 4px 0 var(--mb-lavender),
    0 10px 24px rgba(26, 43, 52, 0.1);
}

.tutor-object-handle {
  background: rgba(240, 220, 247, 0.92);
  color: #60426c;
}

.tutor-object-title {
  color: #60426c;
}

.tutor-object-kind-pill {
  background: rgba(96, 66, 108, 0.12);
  color: #6a4a75;
}

.tutor-object-title-action {
  border: 1px solid rgba(96, 66, 108, 0.18);
  color: #60426c;
}

.tutor-object-title-action:hover {
  border-color: rgba(96, 66, 108, 0.38);
}
```

- [ ] **Step 5: Update remaining warm composer, error, and diagram hard-codes**

Apply these replacements in `frontend/src/styles/session.css`:

```css
.voice-composer {
  background:
    linear-gradient(180deg, rgba(247, 250, 251, 0.9), var(--bg-soft)),
    var(--bg-soft);
}

.ai-card.board-item-diagram.invalid {
  background: rgba(255, 247, 245, 0.92);
}

.session-error {
  box-shadow: 0 12px 28px rgba(26, 43, 52, 0.12);
}
```

Also replace old green alpha colors `rgba(41, 72, 62, ...)` with matching `rgba(43, 98, 88, ...)`, and old shadow colors `rgba(32, 54, 47, ...)` with `rgba(26, 43, 52, ...)`.

- [ ] **Step 6: Run frontend typecheck after CSS session edits**

Run:

```bash
cd frontend && npm run lint
```

Expected: `tsc -b --noEmit` completes with exit code 0.

- [ ] **Step 7: Commit session CSS changes**

Run:

```bash
git add frontend/src/styles/session.css
git commit -m "style: cool session workspace surfaces"
```

## Task 3: Update Ink and Canvas Defaults

**Files:**
- Modify: `frontend/src/components/session/HandwritingPanel.tsx`
- Modify: `frontend/src/components/session/workspaceTypes.ts`
- Modify: `frontend/src/components/session/workspaceReducer.ts`
- Modify: `frontend/src/components/session/BoardInkToolbar.tsx`

- [ ] **Step 1: Update handwriting canvas fill**

In `frontend/src/components/session/HandwritingPanel.tsx`, change:

```ts
const CANVAS_BG = "#fffaf0";
```

to:

```ts
const CANVAS_BG = "#ffffff";
```

- [ ] **Step 2: Update the default green ink type**

In `frontend/src/components/session/workspaceTypes.ts`, change:

```ts
export type InkColor = "#213f35" | "#ff775f" | "#2f6fed" | "#7c4dff";
```

to:

```ts
export type InkColor = "#2b6258" | "#ff775f" | "#2f6fed" | "#7c4dff";
```

- [ ] **Step 3: Update reducer default ink**

In `frontend/src/components/session/workspaceReducer.ts`, change:

```ts
const DEFAULT_INK: InkState = {
  tool: "pen",
  color: "#213f35",
  activeTarget: { kind: "private_board" },
};
```

to:

```ts
const DEFAULT_INK: InkState = {
  tool: "pen",
  color: "#2b6258",
  activeTarget: { kind: "private_board" },
};
```

- [ ] **Step 4: Update ink toolbar swatches**

In `frontend/src/components/session/BoardInkToolbar.tsx`, change:

```ts
const INK_COLORS: InkColor[] = ["#213f35", "#ff775f", "#2f6fed", "#7c4dff"];
```

to:

```ts
const INK_COLORS: InkColor[] = ["#2b6258", "#ff775f", "#2f6fed", "#7c4dff"];
```

- [ ] **Step 5: Search for the old ink color**

Run:

```bash
rg "#213f35|#fffaf0" frontend/src
```

Expected: no output.

- [ ] **Step 6: Run frontend typecheck after TypeScript palette edits**

Run:

```bash
cd frontend && npm run lint
```

Expected: `tsc -b --noEmit` completes with exit code 0.

- [ ] **Step 7: Commit TypeScript palette defaults**

Run:

```bash
git add frontend/src/components/session/HandwritingPanel.tsx frontend/src/components/session/workspaceTypes.ts frontend/src/components/session/workspaceReducer.ts frontend/src/components/session/BoardInkToolbar.tsx
git commit -m "style: update ink palette defaults"
```

## Task 4: Build and Visual Verification

**Files:**
- Verify only; no expected file edits.

- [ ] **Step 1: Run production build**

Run:

```bash
cd frontend && npm run build
```

Expected: `tsc -b && vite build` completes with exit code 0.

- [ ] **Step 2: Start the frontend dev server**

Run:

```bash
cd frontend && npm run dev -- --host 127.0.0.1
```

Expected: Vite prints a localhost URL, usually `http://127.0.0.1:5173/`. Keep the server running for the next step.

- [ ] **Step 3: Verify the library route**

Open `/` in a browser and check:

- Page background reads cool near-white, not cream.
- Dropzone and document rows use mist-grey surfaces and cool borders.
- Primary topbar button hover remains readable.
- No text overlap or layout shift is visible.

- [ ] **Step 4: Verify the session route**

Open `/session` in a browser and check:

- Board background reads mist grey, not saturated blue.
- Handwriting panel is white/cool neutral with the cooler green rail.
- Sticky notes remain yellow.
- Tutor objects remain purple.
- Capture/error controls remain coral/orange.
- Voice composer and board controls use cool neutral surfaces.
- No controls overlap at desktop width and mobile width.

- [ ] **Step 5: Stop the dev server**

Stop the Vite dev server with `Ctrl-C` in its terminal session.

- [ ] **Step 6: Commit verification adjustments if any**

If visual verification required tweaks, commit only those files:

```bash
git add frontend/src/styles/global.css frontend/src/styles/session.css frontend/src/components/session/HandwritingPanel.tsx frontend/src/components/session/workspaceTypes.ts frontend/src/components/session/workspaceReducer.ts frontend/src/components/session/BoardInkToolbar.tsx
git commit -m "style: polish cool palette visual pass"
```

If no tweaks were required, do not create an empty commit.

## Self-Review Notes

- Spec coverage: Tasks 1 and 2 implement Mist Grey app surfaces, borders, and accent preservation. Task 3 updates hard-coded canvas and ink defaults. Task 4 covers typecheck, build, and browser verification on library and session routes.
- Scope control: No backend, layout redesign, component restructuring, or theme switch is included.
- Type consistency: The new default ink `#2b6258` is used consistently in the `InkColor` union, reducer default, and toolbar swatch list.
