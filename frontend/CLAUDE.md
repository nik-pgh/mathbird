# CLAUDE.md — frontend

Scoped guidance for `frontend/`. Root rules in [`../CLAUDE.md`](../CLAUDE.md), architecture in [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md).

## Stack

Vite + React 18 + TypeScript + react-router-dom. UI primitives from `@livekit/components-react`; WebRTC client from `livekit-client`. KaTeX renders typeset math inside whiteboard items. No state library — local `useState` and React Router only.

## Commands

```bash
cd frontend
npm install
npm run dev       # Vite dev server on :5173
npm run lint      # tsc -b --noEmit (typecheck-only; there is no ESLint)
npm run build     # tsc -b && vite build
npm run preview   # serve the built bundle
```

There is no test suite for the frontend yet.

## Routes

| Path | Component | Purpose |
| --- | --- | --- |
| `/` | `pages/UploadPage.tsx` | PDF dropzone + list of uploaded docs. |
| `/session` | `pages/SessionPage.tsx` | Connects to a LiveKit room and renders `SharedReasoningWorkspace` (tutor object cards, handwriting panel, textbook/transcript overlays, voice footer). |

## Rules specific to this package

1. **`src/lib/api.ts` is the only place that calls `fetch()`.** Everything else imports the typed wrappers (`uploadPdf`, `listDocuments`, `requestToken`). If you need a new backend call, add it there.
2. **The backend is not in the audio or whiteboard path.** After `requestToken()`, the page connects directly to LiveKit Cloud via `<LiveKitRoom serverUrl={url} token={token} />`. Audio frames and `ai_board` / `user_board` data-channel messages never touch our FastAPI process.
3. **Voice UI is built from LiveKit React primitives** — `useVoiceAssistant`, `useTrackTranscription`, `useLocalParticipant`, `useDataChannel`, `<BarVisualizer>`, `<RoomAudioRenderer>`. Don't reinvent WebRTC plumbing; the SDK handles it.
4. **Env vars must be `VITE_`-prefixed** (Vite requirement). Read via `import.meta.env.VITE_*`. Defaults in `lib/api.ts` use `http://localhost:8000`.
5. **API request/response shapes match `pydantic.BaseModel`s in `backend/app/api/routes/`.** No schema generator — when you change one side, update the other in the same commit. `UploadedDocument` and `TokenResponse` interfaces in `lib/api.ts` mirror `DocumentResponse` and `TokenResponse` in the backend.
6. **Whiteboard wire types live in `src/lib/whiteboard.ts`** and mirror `backend/app/agent/whiteboard/messages.py`. Same rule: update both sides together. The `useBoardChannel` hook in `src/components/whiteboard/` is a typed wrapper around `useDataChannel(topic)` that handles encode/decode for one topic.
7. **Handwriting snapshots are resized to ≤512px on the long edge before publishing.** That cap matches `BOARD_READER_MAX_IMAGE_DIM` on the backend; keep them aligned if either side changes (`HandwritingPanel.tsx`).
8. **Session chrome lives in `src/components/session/`.** `SessionTopbar.tsx` renders the shared top bar (end-session control included), and `VoiceComposer.tsx` wraps the mic toggle + visualizer via `useTrackToggle` / `useVoiceAssistant`. Reuse these instead of recreating the layout per page.

## Quick "where to add..." map

| Task | File(s) |
| --- | --- |
| New backend call | `src/lib/api.ts` |
| New page / route | New file in `src/pages/`, register in `src/App.tsx` |
| New shared component | `src/components/` |
| New session-page chrome | `src/components/session/` (alongside `SessionTopbar.tsx` / `VoiceComposer.tsx`) |
| New shared hook / util | `src/lib/` |
| Styles | `src/styles/` (`global.css` for app-wide, `session.css` for session-page + whiteboards) |
| New whiteboard item kind | Mirror the pydantic type in `src/lib/whiteboard.ts`, render in `src/components/whiteboard/BoardItem.tsx` |
| New data-channel topic | `src/components/whiteboard/useBoardChannel.ts` (typed wrapper around `useDataChannel`) |
| Backend URL override | `VITE_API_BASE_URL` in `.env.local` |
| LiveKit URL override | `VITE_LIVEKIT_URL` in `.env.local` |

## Gotchas

- `npm run lint` is **typecheck-only** — there's no linter / formatter wired up. Don't claim "lint passes" without saying so.
- `livekit-client` and `@livekit/components-react` must be kept in step with the backend's `livekit-agents` SDK version. Major-version drift breaks transcription / state APIs.
- `tsc -b` uses project references (`tsconfig.app.json`, `tsconfig.node.json`). Don't merge them.
- Vite 8 in `devDependencies` — check release notes before upgrading; plugin compat shifts between majors.
