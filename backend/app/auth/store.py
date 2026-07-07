from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache

from app.config import get_settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  google_sub TEXT NOT NULL UNIQUE,
  email TEXT NOT NULL,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class User:
    id: str
    google_sub: str
    email: str
    name: str
    created_at: str


def stable_user_id(google_sub: str) -> str:
    """Deterministic user id so the same Google account maps to one id everywhere."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"mathbird:{google_sub}"))


class UserStore:
    def __init__(self) -> None:
        settings = get_settings()
        self._conn = sqlite3.connect(settings.auth_db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    def upsert_google_user(self, google_sub: str, email: str, name: str) -> User:
        now = datetime.now(UTC).isoformat()
        user_id = stable_user_id(google_sub)
        row = self._conn.execute(
            """
            INSERT INTO users (id, google_sub, email, name, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(google_sub) DO UPDATE SET
              email = excluded.email,
              name = excluded.name
            RETURNING id, google_sub, email, name, created_at
            """,
            (user_id, google_sub, email, name, now),
        ).fetchone()
        self._conn.commit()
        assert row is not None
        return _row_to_user(row)

    def get_by_id(self, user_id: str) -> User | None:
        row = self._conn.execute(
            "SELECT id, google_sub, email, name, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        return _row_to_user(row)

    def list_users(self, *, limit: int = 20) -> list[User]:
        rows = self._conn.execute(
            """
            SELECT id, google_sub, email, name, created_at
            FROM users
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [_row_to_user(row) for row in rows]


@lru_cache
def get_user_store() -> UserStore:
    return UserStore()


def _row_to_user(row: sqlite3.Row) -> User:
    return User(
        id=row["id"],
        google_sub=row["google_sub"],
        email=row["email"],
        name=row["name"],
        created_at=row["created_at"],
    )
