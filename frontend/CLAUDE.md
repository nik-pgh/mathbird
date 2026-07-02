# CLAUDE.md — frontend

Scoped guidance for `frontend/`. Root rules in [`../CLAUDE.md`](../CLAUDE.md), architecture in [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md).

## Stack

Vite + React 18 + TypeScript + react-router-dom. UI primitives from `@livekit/components-react`; WebRTC client from `livekit-client`. KaTeX renders typeset math; DOMPurify sanitizes HTML/SVG; Mermaid for diagram board items; perfect-freehand for ink strokes. No global state library — local `useState`, context, and reducers only.

## Commands

```bash
cd frontend
npm install
npm run dev       # Vite dev server on :5173
npm run lint      # tsc -b --noEmit (typecheck-only; there is no ESLint)
npm run build     # tsc -b && vite build
npm run preview   # serve the built bundle
npm test          # Node scripts: math, canvas, board placement, pdf layout
```

## Routes

| Path | Component | Auth | Purpose |
| --- | --- | --- | --- |
| `/login` | `pages/LoginPage.tsx` | Public | Google OAuth + optional guest link |
| `/` | `pages/UploadPage.tsx` | `AuthGate` | PDF library — upload then ingest |
| `/session` | `pages/SessionPage.tsx` | `AuthGate` or `?guest=true` | LiveKit voice + `SharedReasoningWorkspace` |
| `/evals` | `pages/EvalDashboardPage.tsx` | Public today | Internal RAG eval dashboard (gate in prod — see improvement plan) |

## Rules specific to this package

1. **`src/lib/api.ts` is the primary `fetch()` site** for documents, token, and syllabus. Session helpers (`getMe`, `logout`) live in `src/lib/auth.ts` today — consolidate into `api.ts` when touching auth.
2. **The backend is not in the audio or whiteboard path.** After `requestToken()`, the page connects directly to LiveKit Cloud via `<LiveKitRoom serverUrl={url} token={token} />`. The LiveKit `url` comes from the token response, not a `VITE_*` env var.
3. **Three data-channel topics:** `ai_board`, `user_board` (see `lib/whiteboard.ts`), and `session_progress` (see `lib/progress.ts` + `lib/roadmapProgress.ts`). Update backend pydantic mirrors in the same commit.
4. **Voice UI is built from LiveKit React primitives** — `useVoiceAssistant`, `useTrackTranscription`, `useLocalParticipant`, `useDataChannel`, `<BarVisualizer>`, `<RoomAudioRenderer>`.
5. **Env vars must be `VITE_`-prefixed** (Vite requirement). Read via `import.meta.env.VITE_*`. Defaults in `lib/api.ts` use `http://localhost:8000`.
6. **API shapes match backend pydantic models** in `backend/app/api/routes/`. No schema generator — update both sides in the same commit.
7. **Handwriting snapshots are resized to ≤512px on the long edge** before publishing (`HandwritingPanel.tsx`). Matches `BOARD_READER_MAX_IMAGE_DIM` on the backend.
8. **Session chrome lives in `src/components/session/`.** Reuse `SessionTopbar`, `VoiceComposer`, `SessionBoardTools`, etc.

## Quick "where to add..." map

| Task | File(s) |
| --- | --- |
| New backend call | `src/lib/api.ts` (and `src/lib/auth.ts` until consolidated) |
| New page / route | New file in `src/pages/`, register in `src/App.tsx` |
| New shared component | `src/components/` |
| New session-page chrome | `src/components/session/` |
| New progress / roadmap UI | `src/components/progress/` |
| New shared hook / util | `src/lib/` |
| Styles | `src/styles/` (`global.css`, `session.css`, `roadmap-progress.css`) |
| New whiteboard item kind | `src/lib/whiteboard.ts` + `src/components/whiteboard/BoardItem.tsx` |
| New data-channel topic | `useBoardChannel.ts` or `useProgressChannel.ts` pattern |
| Backend URL override | `VITE_API_BASE_URL` in `.env.local` |
| Guest login button | `VITE_GUEST_ENABLED` + backend `GUEST_SAMPLE_DOC_ID` |

## Gotchas

- `npm run lint` is **typecheck-only** — no ESLint/Prettier wired up.
- `livekit-client` and `@livekit/components-react` must stay aligned with backend `livekit-agents` SDK version.
- `tsc -b` uses project references (`tsconfig.app.json`, `tsconfig.node.json`).
- Vite 8 in `devDependencies` — check plugin compat before upgrading.
- `VITE_GUEST_ENABLED` is in `.env.example` but must also be added to `vite-env.d.ts` when typing strict checks need it.
- Eval dashboard JSON (~1MB) is eagerly imported today — lazy-load planned (improvement plan Phase 3).
