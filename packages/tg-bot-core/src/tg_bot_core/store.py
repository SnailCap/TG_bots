from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite

from .events import Actor, UserRole


USER_ROLES = frozenset({"user", "trusted", "moderator", "administrator"})


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


@dataclass(frozen=True, slots=True)
class BotUser:
    bot_id: str
    user_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    language_code: str | None = None
    role: UserRole = "user"
    blocked: bool = False
    note: str = ""
    avatar_file_id: str | None = None


@dataclass(frozen=True, slots=True)
class StoredUserAvatar:
    data: bytes
    mime_type: str


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
                CREATE TABLE IF NOT EXISTS bot_users (
                    bot_id TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    language_code TEXT,
                    role TEXT NOT NULL DEFAULT 'user',
                    blocked INTEGER NOT NULL DEFAULT 0,
                    note TEXT NOT NULL DEFAULT '',
                    avatar_file_id TEXT,
                    avatar_mime_type TEXT,
                    avatar_data BLOB,
                    PRIMARY KEY (bot_id, user_id),
                    CHECK (role IN ('user', 'trusted', 'moderator', 'administrator')),
                    CHECK (blocked IN (0, 1))
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
            await self._ensure_bot_user_columns(connection)
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
            actor=Actor(
                actor.user_id,
                actor.chat_id,
                row["username"],
                row["first_name"],
                row["last_name"],
                actor.role,
                actor.language_code,
            ),
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

    async def upsert_user(self, bot_id: str, actor: Actor) -> BotUser:
        """Refresh Telegram identity fields while preserving Studio-managed fields."""

        async with aiosqlite.connect(self.path) as connection:
            connection.row_factory = aiosqlite.Row
            await connection.execute(
                """INSERT INTO bot_users
                (bot_id, user_id, username, first_name, last_name, language_code, role, blocked, note)
                VALUES (?, ?, ?, ?, ?, ?, 'user', 0, '')
                ON CONFLICT(bot_id, user_id) DO UPDATE SET
                    username=excluded.username,
                    first_name=excluded.first_name,
                    last_name=excluded.last_name,
                    language_code=excluded.language_code""",
                (
                    bot_id,
                    actor.user_id,
                    actor.username,
                    actor.first_name,
                    actor.last_name,
                    actor.language_code,
                ),
            )
            row = await (
                await connection.execute(
                    "SELECT * FROM bot_users WHERE bot_id=? AND user_id=?",
                    (bot_id, actor.user_id),
                )
            ).fetchone()
            await connection.commit()
        if row is None:  # Defensive: the upsert and select share one connection.
            raise RuntimeError("User upsert did not produce a row.")
        return self._user_from_row(row)

    async def list_users(self, bot_id: str) -> list[BotUser]:
        async with aiosqlite.connect(self.path) as connection:
            connection.row_factory = aiosqlite.Row
            rows = await (
                await connection.execute(
                    """SELECT * FROM bot_users WHERE bot_id=?
                    ORDER BY lower(coalesce(first_name, '')), lower(coalesce(last_name, '')), user_id""",
                    (bot_id,),
                )
            ).fetchall()
        return [self._user_from_row(row) for row in rows]

    async def update_user(
        self,
        bot_id: str,
        user_id: int,
        *,
        role: UserRole,
        blocked: bool,
        note: str,
    ) -> BotUser | None:
        if role not in USER_ROLES:
            raise ValueError(f"Unsupported user role: {role}")
        async with aiosqlite.connect(self.path) as connection:
            connection.row_factory = aiosqlite.Row
            result = await connection.execute(
                """UPDATE bot_users SET role=?, blocked=?, note=?
                WHERE bot_id=? AND user_id=?""",
                (role, int(blocked), note, bot_id, user_id),
            )
            if result.rowcount != 1:
                return None
            row = await (
                await connection.execute(
                    "SELECT * FROM bot_users WHERE bot_id=? AND user_id=?",
                    (bot_id, user_id),
                )
            ).fetchone()
            await connection.commit()
        return self._user_from_row(row) if row is not None else None

    async def update_user_avatar(
        self,
        bot_id: str,
        user_id: int,
        *,
        file_id: str | None,
        data: bytes | None,
        mime_type: str | None,
    ) -> BotUser | None:
        """Replace or clear a cached profile photo without touching managed fields."""

        if file_id is not None and (not data or not mime_type):
            raise ValueError("A changed profile photo requires data and a MIME type.")
        async with aiosqlite.connect(self.path) as connection:
            connection.row_factory = aiosqlite.Row
            result = await connection.execute(
                """UPDATE bot_users
                SET avatar_file_id=?, avatar_data=?, avatar_mime_type=?
                WHERE bot_id=? AND user_id=?""",
                (file_id, data, mime_type, bot_id, user_id),
            )
            if result.rowcount != 1:
                return None
            row = await (
                await connection.execute(
                    "SELECT * FROM bot_users WHERE bot_id=? AND user_id=?",
                    (bot_id, user_id),
                )
            ).fetchone()
            await connection.commit()
        return self._user_from_row(row) if row is not None else None

    async def get_user_avatar(self, bot_id: str, user_id: int) -> StoredUserAvatar | None:
        async with aiosqlite.connect(self.path) as connection:
            connection.row_factory = aiosqlite.Row
            row = await (
                await connection.execute(
                    """SELECT avatar_data, avatar_mime_type FROM bot_users
                    WHERE bot_id=? AND user_id=?""",
                    (bot_id, user_id),
                )
            ).fetchone()
        if row is None or row["avatar_data"] is None:
            return None
        return StoredUserAvatar(
            data=bytes(row["avatar_data"]),
            mime_type=row["avatar_mime_type"] or "image/jpeg",
        )

    @staticmethod
    async def _ensure_bot_user_columns(connection: aiosqlite.Connection) -> None:
        """Migrate early user-registry databases without discarding durable users."""

        rows = await (await connection.execute("PRAGMA table_info(bot_users)")).fetchall()
        existing = {row[1] for row in rows}
        additions = {
            "language_code": "TEXT",
            "avatar_file_id": "TEXT",
            "avatar_mime_type": "TEXT",
            "avatar_data": "BLOB",
        }
        for name, declaration in additions.items():
            if name not in existing:
                await connection.execute(
                    f"ALTER TABLE bot_users ADD COLUMN {name} {declaration}"
                )

    @staticmethod
    def _user_from_row(row: aiosqlite.Row) -> BotUser:
        return BotUser(
            bot_id=row["bot_id"],
            user_id=row["user_id"],
            username=row["username"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            language_code=row["language_code"],
            role=row["role"],
            blocked=bool(row["blocked"]),
            note=row["note"],
            avatar_file_id=row["avatar_file_id"],
        )
