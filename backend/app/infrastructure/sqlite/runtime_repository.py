from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from collections.abc import Iterator
from typing import Any, Sequence

from app.domain.enums import SessionStatus, VariableType
from app.domain.runtime import RuntimeHistoryEntry
from app.domain.session import InputExpectation, Session
from app.infrastructure.json_codec import dumps_json, loads_json

from .migrations import migrate


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


class SqliteRuntimeRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path.expanduser().resolve(strict=False)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        with self._connect() as connection:
            migrate(connection)

    @classmethod
    def from_project(cls, project_root: Path) -> "SqliteRuntimeRepository":
        return cls(project_root / ".botstudio" / "runtime.db")

    def schema_version(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
            return int(row[0] or 0)

    def get(self, session_id: str) -> Session | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
        return self._session_from_row(row) if row is not None else None

    def find_active(
        self,
        project_id: str,
        telegram_user_id: int,
        telegram_chat_id: int,
    ) -> Session | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM sessions
                WHERE project_id = ?
                  AND telegram_user_id = ?
                  AND telegram_chat_id = ?
                  AND status IN (?, ?)
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (
                    project_id,
                    telegram_user_id,
                    telegram_chat_id,
                    SessionStatus.ACTIVE.value,
                    SessionStatus.WAITING_INPUT.value,
                ),
            ).fetchone()
        return self._session_from_row(row) if row is not None else None

    def save(self, session: Session) -> None:
        waiting = None
        if session.waiting_for_input is not None:
            waiting_data = asdict(session.waiting_for_input)
            waiting_data["expected_type"] = session.waiting_for_input.expected_type.value
            waiting = dumps_json(waiting_data)
        values = (
            session.id,
            session.project_id,
            session.telegram_user_id,
            session.telegram_chat_id,
            session.flow_id,
            session.current_node_id,
            session.status.value,
            dumps_json(session.variables),
            waiting,
            session.flow_schema_version,
            dumps_json(session.metadata),
            _iso(session.created_at),
            _iso(session.updated_at),
        )
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions (
                    id, project_id, telegram_user_id, telegram_chat_id,
                    flow_id, current_node_id, status, variables_json,
                    waiting_input_json, flow_schema_version, metadata_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    project_id = excluded.project_id,
                    telegram_user_id = excluded.telegram_user_id,
                    telegram_chat_id = excluded.telegram_chat_id,
                    flow_id = excluded.flow_id,
                    current_node_id = excluded.current_node_id,
                    status = excluded.status,
                    variables_json = excluded.variables_json,
                    waiting_input_json = excluded.waiting_input_json,
                    flow_schema_version = excluded.flow_schema_version,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                values,
            )
            connection.commit()

    def delete(self, session_id: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            connection.commit()

    def list_for_project(self, project_id: str) -> Sequence[Session]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM sessions WHERE project_id = ? ORDER BY updated_at DESC",
                (project_id,),
            ).fetchall()
        return tuple(self._session_from_row(row) for row in rows)

    def append_history(self, entry: RuntimeHistoryEntry) -> RuntimeHistoryEntry:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO runtime_history (
                    project_id, session_id, event_type, level,
                    message, context_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.project_id,
                    entry.session_id,
                    entry.event_type,
                    entry.level,
                    entry.message,
                    dumps_json(entry.context),
                    _iso(entry.created_at),
                ),
            )
            connection.commit()
            entry_id = int(cursor.lastrowid or 0)
        return replace(entry, id=entry_id)

    def list_history(
        self,
        project_id: str,
        *,
        session_id: str | None = None,
        limit: int = 200,
        after_id: int | None = None,
    ) -> Sequence[RuntimeHistoryEntry]:
        bounded_limit = min(max(1, limit), 2_000)
        clauses = ["project_id = ?"]
        values: list[Any] = [project_id]
        if session_id is not None:
            clauses.append("session_id = ?")
            values.append(session_id)
        if after_id is not None:
            clauses.append("id > ?")
            values.append(after_id)
        order = "ASC" if after_id is not None else "DESC"
        values.append(bounded_limit)
        sql = (
            "SELECT * FROM runtime_history WHERE "
            + " AND ".join(clauses)
            + f" ORDER BY id {order} LIMIT ?"
        )
        with self._connect() as connection:
            rows = connection.execute(sql, tuple(values)).fetchall()
        entries = [self._history_from_row(row) for row in rows]
        if after_id is None:
            entries.reverse()
        return tuple(entries)

    def set_kv(self, project_id: str, key: str, value: Any) -> None:
        if not key.strip():
            raise ValueError("KV key must not be empty")
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO kv_storage(project_id, key, value_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(project_id, key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = excluded.updated_at
                """,
                (project_id, key, dumps_json(value), _iso(datetime.now(UTC))),
            )
            connection.commit()

    def get_kv(self, project_id: str, key: str, default: Any = None) -> Any:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value_json FROM kv_storage WHERE project_id = ? AND key = ?",
                (project_id, key),
            ).fetchone()
        return default if row is None else loads_json(str(row[0]))

    def delete_kv(self, project_id: str, key: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "DELETE FROM kv_storage WHERE project_id = ? AND key = ?",
                (project_id, key),
            )
            connection.commit()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=10.0)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 10000")
            yield connection
        finally:
            connection.close()

    @staticmethod
    def _session_from_row(row: sqlite3.Row) -> Session:
        waiting_raw = row["waiting_input_json"]
        waiting: InputExpectation | None = None
        if waiting_raw is not None:
            data = loads_json(str(waiting_raw))
            waiting = InputExpectation(
                variable_name=str(data["variable_name"]),
                expected_type=VariableType(data.get("expected_type", VariableType.STRING.value)),
                required=bool(data.get("required", True)),
                attempts=int(data.get("attempts", 0)),
                max_attempts=int(data.get("max_attempts", 3)),
                error_message=data.get("error_message"),
            )
        return Session(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            telegram_user_id=int(row["telegram_user_id"]),
            telegram_chat_id=int(row["telegram_chat_id"]),
            flow_id=str(row["flow_id"]),
            current_node_id=str(row["current_node_id"]),
            status=SessionStatus(str(row["status"])),
            variables=dict(loads_json(str(row["variables_json"]))),
            waiting_for_input=waiting,
            flow_schema_version=int(row["flow_schema_version"]),
            metadata=dict(loads_json(str(row["metadata_json"]))),
            created_at=_datetime(str(row["created_at"])),
            updated_at=_datetime(str(row["updated_at"])),
        )

    @staticmethod
    def _history_from_row(row: sqlite3.Row) -> RuntimeHistoryEntry:
        return RuntimeHistoryEntry(
            id=int(row["id"]),
            project_id=str(row["project_id"]),
            session_id=str(row["session_id"]) if row["session_id"] is not None else None,
            event_type=str(row["event_type"]),
            level=str(row["level"]),
            message=str(row["message"]),
            context=dict(loads_json(str(row["context_json"]))),
            created_at=_datetime(str(row["created_at"])),
        )
