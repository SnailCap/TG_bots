from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from app.application.flows import FlowApplicationService
from app.application.projects import ProjectApplicationService
from app.application.scripts import ScriptApplicationService
from app.domain.enums import NodeType, SessionStatus, TransitionKind, VariableType
from app.domain.flow import Flow, Node, NodePosition, Transition
from app.domain.runtime import RuntimeHistoryEntry
from app.domain.session import InputExpectation, Session
from app.infrastructure.events import InMemoryEventBus
from app.infrastructure.project_storage import (
    FilesystemProjectRepository,
    JsonRecentProjectsRepository,
)
from app.infrastructure.scripts import ScriptDiscovery
from app.infrastructure.sqlite import SqliteRuntimeRepository


class ProjectFoundationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addAsyncCleanup(self._cleanup_temporary)
        self.base = Path(self.temporary.name)
        self.data_dir = self.base / "studio-data"
        self.recent_path = self.data_dir / "recent-projects.json"
        self.project_root = self.base / "projects" / "example"
        self.repository = FilesystemProjectRepository()
        self.events = InMemoryEventBus()
        self.projects = ProjectApplicationService(
            self.repository,
            JsonRecentProjectsRepository(self.recent_path),
            self.events,
        )
        self.flows = FlowApplicationService(self.projects, self.repository, self.events)
        self.scripts = ScriptApplicationService(
            self.projects,
            self.repository,
            ScriptDiscovery(),
            self.events,
        )

    async def _cleanup_temporary(self) -> None:
        self.temporary.cleanup()

    async def test_create_open_and_lazy_reopen_from_recent_projects(self) -> None:
        created = await self.projects.create(
            directory=str(self.project_root),
            name="Example bot",
        )

        self.assertEqual(created.path, self.project_root.resolve())
        self.assertEqual(created.project.name, "Example bot")
        self.assertTrue((self.project_root / "bot.json").is_file())
        for directory in ("flows", "scripts", "assets", ".botstudio"):
            self.assertTrue((self.project_root / directory).is_dir())
        self.assertEqual(
            (self.project_root / ".botstudio" / ".gitignore").read_text(
                encoding="utf-8"
            ),
            "*\n!.gitignore\n",
        )

        explicitly_opened = ProjectApplicationService(
            FilesystemProjectRepository(),
            JsonRecentProjectsRepository(self.recent_path),
        )
        reopened = await explicitly_opened.open(str(self.project_root))
        self.assertEqual(reopened.project, created.project)

        after_process_restart = ProjectApplicationService(
            FilesystemProjectRepository(),
            JsonRecentProjectsRepository(self.recent_path),
        )
        lazy = after_process_restart.get(created.project.id)
        self.assertEqual(lazy.project, created.project)
        self.assertEqual(lazy.path, self.project_root.resolve())
        self.assertEqual(after_process_restart.recent()[0].project_id, created.project.id)
        self.assertTrue(after_process_restart.recent()[0].exists)

    async def test_flow_round_trip_is_atomic_and_tree_uses_flow_id(self) -> None:
        opened = await self.projects.create(
            directory=str(self.project_root),
            name="Flow bot",
        )
        flow = Flow(
            id="welcome",
            name="Welcome",
            start_node_id="start",
            nodes=(
                Node(
                    id="start",
                    type=NodeType.START,
                    name="Start",
                    position=NodePosition(x=10.5, y=20.25),
                    config={"greeting": "Привет"},
                ),
                Node(id="end", type=NodeType.END, name="End"),
            ),
            transitions=(
                Transition(
                    id="start-to-end",
                    source_node_id="start",
                    target_node_id="end",
                    kind=TransitionKind.AUTOMATIC,
                    label="continue",
                ),
            ),
            metadata={"editor": {"zoom": 1.25}},
        )

        saved = await self.flows.save(opened.project.id, flow.id, flow)
        loaded = self.flows.get(opened.project.id, flow.id)

        self.assertEqual(saved, flow)
        self.assertEqual(loaded, flow)
        flow_path = self.project_root / "flows" / "welcome.flow.json"
        self.assertTrue(flow_path.is_file())
        self.assertEqual(list(flow_path.parent.glob(f".{flow_path.name}.*.tmp")), [])

        tree = self.projects.tree(opened.project.id)
        flows_directory = next(entry for entry in tree if entry.path == "flows")
        flow_entry = next(entry for entry in flows_directory.children if entry.kind == "flow")
        self.assertEqual(flow_entry.id, flow.id)
        self.assertEqual(flow_entry.name, flow.name)
        self.assertEqual(flow_entry.path, "flows/welcome.flow.json")

    async def test_script_crud_accepts_canonical_and_internal_paths(self) -> None:
        opened = await self.projects.create(
            directory=str(self.project_root),
            name="Script bot",
        )
        project_id = opened.project.id

        created_path = await self.scripts.create(
            project_id,
            "scripts/nested/actions.py",
            "VALUE = 1\n",
        )
        self.assertEqual(created_path, "scripts/nested/actions.py")
        self.assertEqual(self.scripts.list(project_id), ("scripts/nested/actions.py",))
        self.assertEqual(
            self.scripts.read(project_id, "nested/actions.py"),
            "VALUE = 1\n",
        )

        await self.scripts.save(project_id, created_path, "VALUE = 2\n")
        renamed_path = await self.scripts.rename(
            project_id,
            "nested/actions.py",
            "scripts/actions/renamed.py",
        )
        self.assertEqual(renamed_path, "scripts/actions/renamed.py")
        self.assertEqual(self.scripts.read(project_id, renamed_path), "VALUE = 2\n")
        self.assertFalse((self.project_root / "scripts" / "nested").exists())

        await self.scripts.delete(project_id, "actions/renamed.py")
        self.assertEqual(self.scripts.list(project_id), ())
        self.assertFalse((self.project_root / "scripts" / "actions").exists())


class SqliteRuntimeRepositoryTests(unittest.TestCase):
    def test_migrations_and_typed_json_survive_repository_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / ".botstudio" / "runtime.db"
            repository = SqliteRuntimeRepository(database_path)
            timestamp = datetime(2026, 7, 11, 8, 30, 0, tzinfo=UTC)
            calendar_day = date(2026, 7, 12)
            session = Session(
                id="session-1",
                project_id="project-1",
                telegram_user_id=101,
                telegram_chat_id=202,
                flow_id="flow-1",
                current_node_id="ask-name",
                status=SessionStatus.WAITING_INPUT,
                variables={
                    "amount": Decimal("12.340"),
                    "when": timestamp,
                    "day": calendar_day,
                    "nested": [Decimal("0.5"), {"at": timestamp}],
                },
                waiting_for_input=InputExpectation(
                    variable_name="profile.name",
                    expected_type=VariableType.STRING,
                    attempts=1,
                    max_attempts=4,
                    error_message="Try again",
                ),
                metadata={"score": Decimal("99.9")},
                created_at=timestamp,
                updated_at=timestamp,
            )
            repository.save(session)
            repository.set_kv(
                "project-1",
                "typed",
                {"amount": Decimal("1.25"), "day": calendar_day, "at": timestamp},
            )
            history = repository.append_history(
                RuntimeHistoryEntry(
                    project_id="project-1",
                    session_id=session.id,
                    event_type="test.persisted",
                    message="persisted",
                    context={"amount": Decimal("4.2"), "at": timestamp},
                    created_at=timestamp,
                )
            )
            self.assertIsNotNone(history.id)

            reopened = SqliteRuntimeRepository(database_path)
            self.assertEqual(reopened.schema_version(), 2)
            restored = reopened.get(session.id)
            self.assertEqual(restored, session)
            self.assertEqual(
                reopened.find_active("project-1", 101, 202),
                session,
            )
            self.assertEqual(
                reopened.get_kv("project-1", "typed"),
                {"amount": Decimal("1.25"), "day": calendar_day, "at": timestamp},
            )
            self.assertEqual(
                reopened.list_history("project-1")[0].context,
                {"amount": Decimal("4.2"), "at": timestamp},
            )

            connection = sqlite3.connect(database_path)
            try:
                applied = connection.execute(
                    "SELECT version, name FROM schema_migrations ORDER BY version"
                ).fetchall()
            finally:
                connection.close()
            self.assertEqual(
                applied,
                [(1, "initial_runtime_storage"), (2, "runtime_indexes")],
            )


if __name__ == "__main__":
    unittest.main()
