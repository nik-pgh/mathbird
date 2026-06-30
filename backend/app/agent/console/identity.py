"""Interactive doc/user selection for local scripts (agent_console, simulate_conversation)."""

from __future__ import annotations

import asyncio
import sys

from app.auth.store import User, UserStore
from app.config import Settings
from app.documents.catalog import DocumentSummary, list_document_summaries


async def _read_line(prompt: str) -> str:
    return (await asyncio.to_thread(input, prompt)).strip()


def _format_doc_line(index: int, doc: DocumentSummary) -> str:
    flags: list[str] = [doc.status]
    if doc.syllabus_ready:
        flags.append("syllabus")
    suffix = ", ".join(flags)
    short_id = doc.doc_id if len(doc.doc_id) <= 12 else f"{doc.doc_id[:12]}…"
    return f"  [{index}] {short_id}  {doc.filename}  ({suffix})"


async def _prompt_active_doc_id() -> str | None:
    docs = await list_document_summaries()
    print("\nActive document for RAG (search_documents scope):", flush=True)
    if not docs:
        print("  No PDFs in storage. Upload via POST /api/documents first.", flush=True)
        print("  Press Enter to continue without a document filter.", flush=True)
        await _read_line("> ")
        return None

    print("  [0] Skip — no document filter", flush=True)
    for index, doc in enumerate(docs, start=1):
        print(_format_doc_line(index, doc), flush=True)

    while True:
        raw = await _read_line(f"Choose document [0-{len(docs)}]: ")
        if raw == "" or raw == "0":
            return None
        if raw.isdigit():
            choice = int(raw)
            if 1 <= choice <= len(docs):
                selected = docs[choice - 1]
                print(f"  → {selected.filename} ({selected.doc_id})", flush=True)
                return selected.doc_id
        if any(doc.doc_id == raw for doc in docs):
            print(f"  → {raw}", flush=True)
            return raw
        print(f"  Invalid choice {raw!r}. Enter 0-{len(docs)} or a doc_id.", flush=True)


async def _prompt_user_id() -> str | None:
    users: list[User] = []
    try:
        users = UserStore().list_users()
    except Exception:
        users = []

    print("\nUser ID for progress tracking:", flush=True)
    print("  [0] Skip — no progress tools", flush=True)
    for index, user in enumerate(users, start=1):
        print(f"  [{index}] {user.id[:8]}…  {user.email}  ({user.name})", flush=True)
    print("  Or type a custom user id / email", flush=True)

    while True:
        raw = await _read_line("Choose user [0] or enter id: ")
        if raw == "" or raw == "0":
            return None
        if raw.isdigit() and users:
            choice = int(raw)
            if 1 <= choice <= len(users):
                selected = users[choice - 1]
                print(f"  → {selected.email} ({selected.id})", flush=True)
                return selected.id
        for user in users:
            if user.id == raw or user.email == raw:
                print(f"  → {user.email} ({user.id})", flush=True)
                return user.id
        if raw:
            print(f"  → custom user {raw!r}", flush=True)
            return raw
        print("  Invalid choice. Enter 0, a list number, or a user id.", flush=True)


async def prompt_console_identity(
    settings: Settings,
    *,
    need_user: bool,
    need_doc: bool,
) -> tuple[str | None, str | None]:
    """Prompt on stdin when env identity is incomplete. Returns ``(user_id, doc_id)``."""
    if not (need_user or need_doc):
        return None, None

    if not settings.sim_interactive or not sys.stdin.isatty():
        return None, None

    print("\n── mathbird console setup ──", flush=True)
    active_doc_id = await _prompt_active_doc_id() if need_doc else None
    user_id = await _prompt_user_id() if need_user else None
    print("", flush=True)
    return user_id, active_doc_id


async def resolve_local_identity(settings: Settings) -> tuple[str | None, str | None]:
    """Resolve ``SIM_*`` env vars and optional stdin prompts for local scripts."""
    user_id = settings.sim_user_id or None
    active_doc_id = settings.sim_active_doc_id or None
    prompted_user, prompted_doc = await prompt_console_identity(
        settings,
        need_user=user_id is None,
        need_doc=active_doc_id is None,
    )
    return user_id or prompted_user, active_doc_id or prompted_doc
