from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite

from .events import Actor


def utc_now() -> datetime:
    return datetime.now(UTC)


def to_timestamp(value: datetime) -> float:
    return value.timestamp()


@dataclass(frozen=True, slots=True)
class FlowSession:
    bot_id: str
    actor: Actor
    flow_id: str | None = None
    state_id: str | None = None
    view_id: str | None = None
    variables: dict[str, Any] | None = None
    status: str = "idle"
    revision: int = 0
    updated_at: datetime | None = None


class SessionConflict(RuntimeError):
    pass


class SqliteStore:
    """SQLite persistence shared by flow sessions, deduplication and durable jobs."""

    def __init__(self, path: Path) -> None:
        self.path = path

    async def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.path) as connection:
            await connection.execute("PRAGMA journal_mode=WAL")
            await connection.execute("PRAGMA foreign_keys=ON")
            await connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS flow_sessions (
                    bot_id TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    flow_id TEXT,
                    state_id TEXT,
                    view_id TEXT,
                    variables_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (bot_id, user_id, chat_id)
                );
                CREATE TABLE IF NOT EXISTS processed_updates (
                    bot_id TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    update_id INTEGER NOT NULL,
                    processed_at REAL NOT NULL,
                    PRIMARY KEY (bot_id, user_id, chat_id, update_id)
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    handler_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    run_at REAL NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL,
                    max_attempts INTEGER NOT NULL,
                    lease_until REAL,
                    last_error TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS jobs_due_idx ON jobs (status, run_at);
                CREATE TABLE IF NOT EXISTS schedules (
                    id TEXT PRIMARY KEY,
                    handler_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    interval_seconds REAL NOT NULL,
                    next_run_at REAL NOT NULL,
                    active INTEGER NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS job_runs (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    started_at REAL NOT NULL,
                    finished_at REAL,
                    status TEXT NOT NULL,
                    error TEXT
                );
                """
            )
            await connection.commit()

    async def load_session(self, bot_id: str, actor: Actor) -> FlowSession:
        async with aiosqlite.connect(self.path) as connection:
            connection.row_factory = aiosqlite.Row
            row = await (
                await connection.execute(
                    "SELECT * FROM flow_sessions WHERE bot_id=? AND user_id=? AND chat_id=?",
                    (bot_id, actor.user_id, actor.chat_id),
                )
            ).fetchone()
        if row is None:
            return FlowSession(bot_id=bot_id, actor=actor, variables={}, updated_at=utc_now())
        return FlowSession(
            bot_id=bot_id,
            actor=Actor(actor.user_id, actor.chat_id, row["username"], row["first_name"], row["last_name"]),
            flow_id=row["flow_id"],
            state_id=row["state_id"],
            view_id=row["view_id"],
            variables=json.loads(row["variables_json"]),
            status=row["status"],
            revision=row["revision"],
            updated_at=datetime.fromtimestamp(row["updated_at"], UTC),
        )

    async def save_session(self, session: FlowSession) -> FlowSession:
        now = utc_now()
        variables = json.dumps(session.variables or {}, ensure_ascii=False, allow_nan=False)
        async with aiosqlite.connect(self.path) as connection:
            if session.revision == 0:
                try:
                    await connection.execute(
                        """INSERT INTO flow_sessions
                        (bot_id, user_id, chat_id, username, first_name, last_name, flow_id, state_id,
                         view_id, variables_json, status, revision, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            session.bot_id,
                            session.actor.user_id,
                            session.actor.chat_id,
                            session.actor.username,
                            session.actor.first_name,
                            session.actor.last_name,
                            session.flow_id,
                            session.state_id,
                            session.view_id,
                            variables,
                            session.status,
                            1,
                            to_timestamp(now),
                        ),
                    )
                except aiosqlite.IntegrityError as error:
                    raise SessionConflict("Session was created by another update.") from error
                revision = 1
            else:
                result = await connection.execute(
                    """UPDATE flow_sessions SET username=?, first_name=?, last_name=?, flow_id=?, state_id=?,
                    view_id=?, variables_json=?, status=?, revision=?, updated_at=?
                    WHERE bot_id=? AND user_id=? AND chat_id=? AND revision=?""",
                    (
                        session.actor.username,
                        session.actor.first_name,
                        session.actor.last_name,
                        session.flow_id,
                        session.state_id,
                        session.view_id,
                        variables,
                        session.status,
                        session.revision + 1,
                        to_timestamp(now),
                        session.bot_id,
                        session.actor.user_id,
                        session.actor.chat_id,
                        session.revision,
                    ),
                )
                if result.rowcount != 1:
                    raise SessionConflict("Session changed while this update was being processed.")
                revision = session.revision + 1
            await connection.commit()
        return replace(session, revision=revision, updated_at=now)

    async def mark_update_once(self, bot_id: str, actor: Actor, update_id: int) -> bool:
        async with aiosqlite.connect(self.path) as connection:
            try:
                await connection.execute(
                    "INSERT INTO processed_updates VALUES (?, ?, ?, ?, ?)",
                    (bot_id, actor.user_id, actor.chat_id, update_id, to_timestamp(utc_now())),
                )
            except aiosqlite.IntegrityError:
                return False
            await connection.commit()
        return True
