from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    sql: str


MIGRATIONS = (
    Migration(
        version=1,
        name="initial_runtime_storage",
        sql="""
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            telegram_user_id INTEGER NOT NULL,
            telegram_chat_id INTEGER NOT NULL,
            flow_id TEXT NOT NULL,
            current_node_id TEXT NOT NULL,
            status TEXT NOT NULL,
            variables_json TEXT NOT NULL,
            waiting_input_json TEXT,
            flow_schema_version INTEGER NOT NULL DEFAULT 1,
            metadata_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE runtime_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            session_id TEXT,
            event_type TEXT NOT NULL,
            level TEXT NOT NULL,
            message TEXT NOT NULL,
            context_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE kv_storage (
            project_id TEXT NOT NULL,
            key TEXT NOT NULL,
            value_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (project_id, key)
        );
        """,
    ),
    Migration(
        version=2,
        name="runtime_indexes",
        sql="""
        CREATE INDEX ix_sessions_project_user_chat_status
            ON sessions(project_id, telegram_user_id, telegram_chat_id, status, updated_at);
        CREATE INDEX ix_sessions_project_updated
            ON sessions(project_id, updated_at);
        CREATE INDEX ix_runtime_history_project_id
            ON runtime_history(project_id, id);
        CREATE INDEX ix_runtime_history_session_id
            ON runtime_history(session_id, id);
        """,
    ),
)


def migrate(connection: sqlite3.Connection) -> int:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    applied = {
        int(row[0])
        for row in connection.execute("SELECT version FROM schema_migrations").fetchall()
    }
    for migration in MIGRATIONS:
        if migration.version in applied:
            continue
        connection.executescript(migration.sql)
        connection.execute(
            "INSERT INTO schema_migrations(version, name) VALUES (?, ?)",
            (migration.version, migration.name),
        )
        connection.commit()
    return MIGRATIONS[-1].version if MIGRATIONS else 0

