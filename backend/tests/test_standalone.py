from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import textwrap

from fastapi.testclient import TestClient

from app.api.app import create_app


def test_generated_project_runs_without_studio_runtime_and_restores_session(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app())
    created = client.post(
        "/api/v1/projects",
        json={"parent_path": str(tmp_path), "name": "Standalone Bot"},
    )
    assert created.status_code == 200
    workspace = created.json()
    project_id = workspace["project_id"]
    root = Path(workspace["project_root"])

    done = client.post(
        f"/api/v1/projects/{project_id}/views",
        json={
            "id": "done",
            "payload": {"text": {"inline": "Done {{ result }}"}, "keyboard": []},
        },
    )
    assert done.status_code == 200
    home = client.get(f"/api/v1/projects/{project_id}/views/home").json()
    home_payload = home["payload"]
    home_payload["keyboard"] = [
        [
            {
                "id": "confirm_button",
                "text": "Confirm",
                "action": {"type": "flow.event", "target": "confirm"},
            }
        ]
    ]
    saved_home = client.put(
        f"/api/v1/projects/{project_id}/views/home",
        json={"payload": home_payload, "revision": home["revision"]},
    )
    assert saved_home.status_code == 200
    flow = client.get(f"/api/v1/projects/{project_id}/flows/home").json()
    handlers = client.get(f"/api/v1/projects/{project_id}/handlers").json()
    scaffolded = client.post(
        f"/api/v1/projects/{project_id}/handlers",
        json={
            "handler_id": "home.confirm",
            "kind": "button",
            "registry_revision": handlers["revision"],
            "attachment": {
                "type": "flow_event",
                "flow_id": "home",
                "state_id": "home",
                "event_id": "confirm",
            },
            "target_revision": flow["revision"],
            "routes": {"success": {"type": "view.render", "target": "done"}},
        },
    )
    assert scaffolded.status_code == 200
    handler = scaffolded.json()
    source = Path(handler["open_target"]["file_path"])
    source.write_text(
        "from tg_bot_core import ButtonContext, HandlerResult\n\n\n"
        "async def handle(ctx: ButtonContext) -> HandlerResult:\n"
        "    return HandlerResult.success(values={'result': 'ok'})\n",
        encoding="utf-8",
    )
    validation = client.get(
        f"/api/v1/projects/{project_id}/validation"
    ).json()["issues"]
    assert not [item for item in validation if item["level"] == "error"]

    repository = Path(__file__).resolve().parents[2]
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONPATH"] = os.pathsep.join(
        (str(root / "src"), str(repository / "packages" / "tg-bot-core" / "src"))
    )

    entrypoint = subprocess.run(
        [sys.executable, "-m", workspace["package"], "--validate"],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert entrypoint.returncode == 0, entrypoint.stdout + entrypoint.stderr

    probe = textwrap.dedent(
        """
        import asyncio
        from pathlib import Path
        import sys

        from tg_bot_core import Actor, BotApp, BotConfig, CallbackEvent, CommandEvent


        class FakeTransport:
            def __init__(self):
                self.handler = None
                self.messages = []

            async def start(self, handler):
                self.handler = handler

            async def stop(self):
                return None

            async def send(self, message):
                self.messages.append(message)


        async def scenario(root):
            database = root / "data" / "runtime.sqlite3"
            actor = Actor(user_id=1, chat_id=10)
            first_transport = FakeTransport()
            first = BotApp(
                config=BotConfig(root, None, database),
                services=[],
                transport=first_transport,
            )
            await first.start()
            await first.handle_event(CommandEvent(actor, 1, "start"))
            assert first_transport.messages[-1].text.strip() == "Welcome to your bot!"
            await first.handle_event(CallbackEvent(actor, 2, "confirm_button"))
            assert first_transport.messages[-1].text == "Done ok"
            await first.stop()

            second_transport = FakeTransport()
            restarted = BotApp(
                config=BotConfig(root, None, database),
                services=[],
                transport=second_transport,
            )
            await restarted.start()
            await restarted.handle_event(
                CallbackEvent(actor, 3, "missing_stale_action")
            )
            assert second_transport.messages[-1].text == "Done ok"
            await restarted.stop()


        assert not any(
            name == "app" or name.startswith("app.") for name in sys.modules
        )
        asyncio.run(scenario(Path(sys.argv[1])))
        assert not any(
            name == "app" or name.startswith("app.") for name in sys.modules
        )
        """
    )
    runtime = subprocess.run(
        [sys.executable, "-c", probe, str(root)],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert runtime.returncode == 0, runtime.stdout + runtime.stderr

    generated = "\n".join(
        path.read_text(encoding="utf-8") for path in (root / "src").rglob("*.py")
    )
    assert "from app" not in generated
    assert "backend" not in generated
