"""Persistent session storage for the Swarm TUI."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .session import Session


DEFAULT_DB_PATH = Path("swarm_sessions.db")


class SessionStore:
    """SQLite-backed store for TUI sessions."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path), check_same_thread=False)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    messages TEXT NOT NULL DEFAULT '[]',
                    results TEXT NOT NULL DEFAULT '[]'
                )
                """
            )
            conn.commit()

    def save(self, session: "Session") -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (id, title, created_at, updated_at, messages, results)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    updated_at = excluded.updated_at,
                    messages = excluded.messages,
                    results = excluded.results
                """,
                (
                    session.id,
                    session.title,
                    session.created_at,
                    session.updated_at,
                    json.dumps(session.messages, default=str),
                    json.dumps(session.results, default=str),
                ),
            )
            conn.commit()

    def load(self, session_id: str) -> "Session | None":
        from .session import Session

        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, title, created_at, updated_at, messages, results FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        if not row:
            return None
        return Session(
            id=row[0],
            title=row[1],
            created_at=row[2],
            updated_at=row[3],
            messages=json.loads(row[4]) if row[4] else [],
            results=json.loads(row[5]) if row[5] else [],
        )

    def list_sessions(self) -> list["Session"]:
        from .session import Session

        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, title, created_at, updated_at, messages, results FROM sessions ORDER BY updated_at DESC"
            ).fetchall()
        return [
            Session(
                id=r[0],
                title=r[1],
                created_at=r[2],
                updated_at=r[3],
                messages=json.loads(r[4]) if r[4] else [],
                results=json.loads(r[5]) if r[5] else [],
            )
            for r in rows
        ]

    def delete(self, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()
