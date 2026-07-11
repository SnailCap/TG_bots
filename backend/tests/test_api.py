from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.api.container import AppContainer
from app.domain.project import BotIdentity
from app.infrastructure.secrets import MemorySecretStore
from app.infrastructure.sqlite import SqliteRuntimeRepository
from app.runtime import RuntimeManager, RuntimeRepositories, StandardRuntimeFactory
from tests.fakes.telegram import FakeTelegramPort


class AcceptingTokenValidator:
    def __init__(self) -> None:
        self.tokens: list[str] = []

    async def validate(self, token: str) -> BotIdentity:
        self.tokens.append(token)
        return BotIdentity(
            bot_id=123456,
            username="test_studio_bot",
            display_name="Studio Test Bot",
        )


class ApiIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.data_dir = self.base / "studio-data"
        self.project_root = self.base / "projects" / "example"
        self.secrets = MemorySecretStore()
        self.validator = AcceptingTokenValidator()
        self.container = AppContainer.build(
            data_dir=self.data_dir,
            secret_store=self.secrets,
            token_validator=self.validator,
        )
        self.runtime_tokens: list[str] = []
        self.telegram_adapters: list[FakeTelegramPort] = []

        def telegram_factory(token: str) -> FakeTelegramPort:
            self.runtime_tokens.append(token)
            adapter = FakeTelegramPort()
            self.telegram_adapters.append(adapter)
            return adapter

        def repository_factory(project_root: Path) -> RuntimeRepositories:
            repository = SqliteRuntimeRepository.from_project(project_root)
            return RuntimeRepositories(sessions=repository, storage=repository)

        self.container.runtime_manager = RuntimeManager(
            StandardRuntimeFactory(
                projects=self.container.project_repository,
                telegram_factory=telegram_factory,
                repository_factory=repository_factory,
                publisher=self.container.events,
            )
        )
        self.client = TestClient(create_app(self.container))
        self.client.__enter__()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        self.temporary.cleanup()

    def _create_project(self, *, name: str = "API bot") -> dict:
        response = self.client.post(
            "/api/v1/projects",
            json={"directory": str(self.project_root), "name": name},
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_project_flow_tree_and_script_crud_over_http(self) -> None:
        project = self._create_project()
        project_id = project["id"]

        flow_response = self.client.post(
            f"/api/v1/projects/{project_id}/flows",
            json={"name": "Welcome"},
        )
        self.assertEqual(flow_response.status_code, 201, flow_response.text)
        flow = flow_response.json()
        loaded_flow = self.client.get(
            f"/api/v1/projects/{project_id}/flows/{flow['id']}"
        )
        self.assertEqual(loaded_flow.status_code, 200, loaded_flow.text)
        self.assertEqual(loaded_flow.json(), flow)

        tree_response = self.client.get(f"/api/v1/projects/{project_id}/tree")
        self.assertEqual(tree_response.status_code, 200, tree_response.text)
        flows_directory = next(
            entry for entry in tree_response.json() if entry["path"] == "flows"
        )
        self.assertEqual(flows_directory["children"][0]["id"], flow["id"])

        created_script = self.client.post(
            f"/api/v1/projects/{project_id}/scripts",
            json={
                "path": "scripts/nested/action.py",
                "content": "VALUE = 1\n",
            },
        )
        self.assertEqual(created_script.status_code, 201, created_script.text)
        self.assertEqual(created_script.json()["path"], "scripts/nested/action.py")

        saved_script = self.client.put(
            f"/api/v1/projects/{project_id}/scripts",
            json={
                "path": "nested/action.py",
                "content": "VALUE = 2\n",
            },
        )
        self.assertEqual(saved_script.status_code, 200, saved_script.text)
        action_source = """
from bot_engine import action, ActionResult

@action("nested_action")
async def nested_action(context):
    return ActionResult.success()
""".lstrip()
        action_save = self.client.put(
            f"/api/v1/projects/{project_id}/scripts",
            json={"path": "nested/action.py", "content": action_source},
        )
        self.assertEqual(action_save.status_code, 200, action_save.text)
        actions = self.client.get(
            f"/api/v1/projects/{project_id}/scripts/actions"
        )
        self.assertEqual(actions.status_code, 200, actions.text)
        self.assertEqual(
            actions.json()["actions"][0]["file_path"],
            "scripts/nested/action.py",
        )
        renamed_script = self.client.patch(
            f"/api/v1/projects/{project_id}/scripts",
            json={
                "path": "scripts/nested/action.py",
                "new_path": "scripts/renamed.py",
            },
        )
        self.assertEqual(renamed_script.status_code, 200, renamed_script.text)
        self.assertEqual(renamed_script.json()["path"], "scripts/renamed.py")
        read_script = self.client.get(
            f"/api/v1/projects/{project_id}/scripts/content",
            params={"path": "renamed.py"},
        )
        self.assertEqual(read_script.status_code, 200, read_script.text)
        self.assertEqual(read_script.json()["content"], action_source)
        deleted_script = self.client.delete(
            f"/api/v1/projects/{project_id}/scripts",
            params={"path": "scripts/renamed.py"},
        )
        self.assertEqual(deleted_script.status_code, 204, deleted_script.text)
        self.assertEqual(
            self.client.get(f"/api/v1/projects/{project_id}/scripts").json(),
            [],
        )

    def test_recent_project_is_lazy_reopened_by_a_fresh_api_container(self) -> None:
        project = self._create_project(name="Persistent bot")

        self.client.__exit__(None, None, None)
        fresh_container = AppContainer.build(
            data_dir=self.data_dir,
            secret_store=MemorySecretStore(),
            token_validator=AcceptingTokenValidator(),
        )
        self.client = TestClient(create_app(fresh_container))
        self.client.__enter__()

        response = self.client.get(f"/api/v1/projects/{project['id']}")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["id"], project["id"])
        self.assertEqual(Path(response.json()["path"]), self.project_root.resolve())

    def test_telegram_token_never_appears_in_api_or_project_file(self) -> None:
        project = self._create_project(name="Secret bot")
        project_id = project["id"]
        token = "123456:super-secret-token-material"

        response = self.client.put(
            f"/api/v1/projects/{project_id}/token",
            json={"token": token},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.validator.tokens, [token])
        self.assertNotIn(token, response.text)

        project_response = self.client.get(f"/api/v1/projects/{project_id}")
        settings_response = self.client.get(
            f"/api/v1/projects/{project_id}/settings"
        )
        self.assertEqual(project_response.status_code, 200, project_response.text)
        self.assertEqual(settings_response.status_code, 200, settings_response.text)
        combined_api_json = json.dumps(
            [project_response.json(), settings_response.json()],
            ensure_ascii=False,
        )
        self.assertNotIn(token, combined_api_json)

        configuration = settings_response.json()
        self.assertTrue(configuration["secret_configured"])
        secret_ref = configuration["secret_ref"]
        self.assertEqual(self.secrets.get(secret_ref), token)
        self.assertNotIn(token, (self.project_root / "bot.json").read_text(encoding="utf-8"))

    def test_runtime_status_run_logs_and_stop_with_fake_telegram(self) -> None:
        project = self._create_project(name="Runtime API bot")
        project_id = project["id"]
        flow_response = self.client.post(
            f"/api/v1/projects/{project_id}/flows",
            json={"name": "Main"},
        )
        self.assertEqual(flow_response.status_code, 201, flow_response.text)
        flow_id = flow_response.json()["id"]
        settings_response = self.client.patch(
            f"/api/v1/projects/{project_id}/settings",
            json={"start_flow_id": flow_id, "start_behavior": "reset"},
        )
        self.assertEqual(settings_response.status_code, 200, settings_response.text)

        initial = self.client.get(f"/api/v1/projects/{project_id}/runtime/status")
        self.assertEqual(initial.status_code, 200, initial.text)
        self.assertEqual(initial.json()["state"], "stopped")
        self.assertFalse(initial.json()["telegram_connected"])

        missing_token = self.client.post(
            f"/api/v1/projects/{project_id}/runtime/run"
        )
        self.assertEqual(missing_token.status_code, 422, missing_token.text)
        self.assertEqual(
            missing_token.json()["error"]["code"],
            "token_validation_failed",
        )

        token = "123456:runtime-secret-token"
        token_response = self.client.put(
            f"/api/v1/projects/{project_id}/token",
            json={"token": token},
        )
        self.assertEqual(token_response.status_code, 200, token_response.text)

        started = self.client.post(f"/api/v1/projects/{project_id}/runtime/run")
        self.assertEqual(started.status_code, 200, started.text)
        self.assertEqual(started.json()["state"], "running")
        self.assertTrue(started.json()["telegram_connected"])
        self.assertEqual(
            started.json()["bot_identity"]["username"],
            "studio_test_bot",
        )
        self.assertEqual(self.runtime_tokens, [token])
        self.assertNotIn(token, started.text)
        self.assertTrue(self.telegram_adapters[0].is_running)

        logs = self.client.get(f"/api/v1/projects/{project_id}/runtime/logs")
        self.assertEqual(logs.status_code, 200, logs.text)
        event_types = [entry["event_type"] for entry in logs.json()]
        self.assertIn("runtime.starting", event_types)
        self.assertIn("runtime.started", event_types)

        stopped = self.client.post(f"/api/v1/projects/{project_id}/runtime/stop")
        self.assertEqual(stopped.status_code, 200, stopped.text)
        self.assertEqual(stopped.json()["state"], "stopped")
        self.assertFalse(stopped.json()["telegram_connected"])
        self.assertFalse(self.telegram_adapters[0].is_running)

        final_status = self.client.get(
            f"/api/v1/projects/{project_id}/runtime/status"
        )
        self.assertEqual(final_status.status_code, 200, final_status.text)
        self.assertEqual(final_status.json()["state"], "stopped")
        final_logs = self.client.get(f"/api/v1/projects/{project_id}/runtime/logs")
        self.assertIn(
            "runtime.stopped",
            [entry["event_type"] for entry in final_logs.json()],
        )


if __name__ == "__main__":
    unittest.main()
