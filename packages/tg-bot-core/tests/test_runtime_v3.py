from __future__ import annotations

import asyncio
from pathlib import Path
import signal

import pytest

from tg_bot_core import (
    Actor,
    BotApp,
    BotConfig,
    CallbackEvent,
    CommandEvent,
    MessageEvent,
    ServiceProvider,
)
from tg_bot_core.store import SessionConflict

from conftest import FakeTransport, make_project, write_handler


def make_interactive_project(root: Path, *, start_policy: str = "reset") -> Path:
    views = [
        {
            "schema_version": 3,
            "id": "home",
            "text": {"inline": "Home"},
            "keyboard": [[{"id": "begin_main", "text": "Begin", "action": {"type": "flow.start", "target": "main"}}]],
        },
        {"schema_version": 3, "id": "ask", "text": {"inline": "Ask {{ started }}"}, "keyboard": []},
        {
            "schema_version": 3,
            "id": "confirm",
            "text": {"inline": "Confirm {{ answer }}"},
            "keyboard": [[
                {"id": "confirm_order", "text": "Confirm", "action": {"type": "flow.event", "target": "confirm"}},
                {"id": "cancel_order", "text": "Cancel", "action": {"type": "flow.cancel", "view": "cancelled"}},
            ]],
        },
        {"schema_version": 3, "id": "done", "text": {"inline": "Done {{ answer }}"}, "keyboard": []},
        {"schema_version": 3, "id": "cancelled", "text": {"inline": "Cancelled"}, "keyboard": []},
        {"schema_version": 3, "id": "help", "text": {"inline": "Help"}, "keyboard": []},
        {"schema_version": 3, "id": "message_fallback", "text": {"inline": "Message fallback"}, "keyboard": []},
        {"schema_version": 3, "id": "command_fallback", "text": {"inline": "Command fallback"}, "keyboard": []},
        {"schema_version": 3, "id": "error", "text": {"inline": "Handled error"}, "keyboard": []},
        {"schema_version": 3, "id": "broken", "text": {"inline": "{{ unavailable }}"}, "keyboard": []},
    ]
    handlers = [
        {"id": "life.start", "module": "fixture_bot.handlers.life_start", "symbol": "handle", "kind": "lifecycle"},
        {"id": "life.enter", "module": "fixture_bot.handlers.life_enter", "symbol": "handle", "kind": "lifecycle"},
        {"id": "life.confirm", "module": "fixture_bot.handlers.life_confirm", "symbol": "handle", "kind": "lifecycle"},
        {"id": "life.complete", "module": "fixture_bot.handlers.life_complete", "symbol": "handle", "kind": "lifecycle"},
        {"id": "life.cancel", "module": "fixture_bot.handlers.life_cancel", "symbol": "handle", "kind": "lifecycle"},
        {"id": "life.error", "module": "fixture_bot.handlers.life_error", "symbol": "handle", "kind": "lifecycle"},
        {
            "id": "profile.save",
            "module": "fixture_bot.handlers.profile_save",
            "symbol": "handle",
            "kind": "message",
            "outcomes": ["invalid", "broken"],
        },
        {"id": "order.submit", "module": "fixture_bot.handlers.order_submit", "symbol": "handle", "kind": "button"},
        {"id": "fallback.message", "module": "fixture_bot.handlers.fallback_message", "symbol": "handle", "kind": "message"},
        {"id": "fallback.command", "module": "fixture_bot.handlers.fallback_command", "symbol": "handle", "kind": "command"},
    ]
    flow = {
        "schema_version": 3,
        "id": "main",
        "initial_state": "ask",
        "lifecycle": {
            "on_start": {"handler": "life.start", "outcomes": {"success": {"type": "noop"}}},
            "on_complete": {"handler": "life.complete", "outcomes": {"success": {"type": "noop"}}},
            "on_cancel": {"handler": "life.cancel", "outcomes": {"success": {"type": "noop"}}},
            "on_error": {
                "handler": "life.error",
                "outcomes": {"success": {"type": "view.render", "target": "error"}},
            },
        },
        "states": {
            "ask": {
                "view": "ask",
                "on_enter": {"handler": "life.enter", "outcomes": {"success": {"type": "noop"}}},
                "on_message": {
                    "handler": "profile.save",
                    "outcomes": {
                        "success": {"type": "flow.goto", "target": "confirm"},
                        "invalid": {"type": "view.render", "target": "ask"},
                        "broken": {"type": "view.render", "target": "broken"},
                    },
                },
            },
            "confirm": {
                "view": "confirm",
                "on_enter": {"handler": "life.confirm", "outcomes": {"success": {"type": "noop"}}},
                "events": {
                    "confirm": {
                        "handler": "order.submit",
                        "outcomes": {"success": {"type": "flow.finish", "view": "done"}},
                    }
                },
            },
        },
    }
    commands = {
        "commands": [
            {"name": "help", "action": {"type": "view.render", "target": "help"}},
            {"name": "begin", "action": {"type": "flow.start", "target": "main"}},
        ],
        "message_fallback": {
            "type": "handler.invoke",
            "handler": "fallback.message",
            "outcomes": {"success": {"type": "view.render", "target": "message_fallback"}},
        },
        "command_fallback": {
            "type": "handler.invoke",
            "handler": "fallback.command",
            "outcomes": {"success": {"type": "view.render", "target": "command_fallback"}},
        },
    }
    make_project(
        root,
        bot={"start": {"flow": "main", "policy": start_policy}},
        views=views,
        flows=[flow],
        handlers=handlers,
        commands=commands,
    )
    sources = {
        "life_start": """from tg_bot_core import HandlerResult, LifecycleContext
async def handle(ctx: LifecycleContext) -> HandlerResult:
    ctx.services["trace"].append("start")
    return HandlerResult.success(values={"started": True})
""",
        "life_enter": """from tg_bot_core import HandlerResult, LifecycleContext
async def handle(ctx: LifecycleContext) -> HandlerResult:
    ctx.services["trace"].append("enter:ask")
    return HandlerResult.success()
""",
        "life_confirm": """from tg_bot_core import HandlerResult, LifecycleContext
async def handle(ctx: LifecycleContext) -> HandlerResult:
    ctx.services["trace"].append("enter:confirm")
    return HandlerResult.success()
""",
        "life_complete": """from tg_bot_core import HandlerResult, LifecycleContext
async def handle(ctx: LifecycleContext) -> HandlerResult:
    ctx.services["trace"].append("complete")
    return HandlerResult.success()
""",
        "life_cancel": """from tg_bot_core import HandlerResult, LifecycleContext
async def handle(ctx: LifecycleContext) -> HandlerResult:
    ctx.services["trace"].append("cancel")
    return HandlerResult.success()
""",
        "life_error": """from tg_bot_core import HandlerResult, LifecycleContext
async def handle(ctx: LifecycleContext) -> HandlerResult:
    ctx.services["trace"].append("error:" + ctx.payload["error"])
    return HandlerResult.success()
""",
        "profile_save": """from tg_bot_core import HandlerResult, MessageContext
async def handle(ctx: MessageContext) -> HandlerResult:
    ctx.services["trace"].append("message:" + ctx.event.text)
    ctx.state.set("state_only", "kept")
    if ctx.event.text == "invalid":
        return HandlerResult.outcome("invalid")
    if ctx.event.text == "broken":
        return HandlerResult.outcome("broken")
    if ctx.event.text == "explode":
        return None
    return HandlerResult.success(values={"answer": ctx.event.text})
""",
        "order_submit": """from tg_bot_core import ButtonContext, HandlerResult
async def handle(ctx: ButtonContext) -> HandlerResult:
    ctx.services["trace"].append("submit")
    return HandlerResult.success()
""",
        "fallback_message": """from tg_bot_core import HandlerResult, MessageContext
async def handle(ctx: MessageContext) -> HandlerResult:
    ctx.services["trace"].append("fallback:message")
    return HandlerResult.success()
""",
        "fallback_command": """from tg_bot_core import CommandContext, HandlerResult
async def handle(ctx: CommandContext) -> HandlerResult:
    ctx.services["trace"].append("fallback:command")
    return HandlerResult.success()
""",
    }
    for name, source in sources.items():
        write_handler(root, f"fixture_bot.handlers.{name}", source)
    return root


def new_app(root: Path, transport: FakeTransport, trace: list[str], *, max_auto_transitions: int = 32) -> BotApp:
    return BotApp(
        config=BotConfig(
            project_root=root,
            token=None,
            database_path=root / "data" / "runtime.sqlite3",
            max_auto_transitions=max_auto_transitions,
        ),
        services=[ServiceProvider("trace", lambda _container: trace)],
        transport=transport,
    )


@pytest.mark.asyncio
async def test_callback_navigation_edits_the_current_message_by_default_and_can_send_new(tmp_path: Path) -> None:
    make_project(
        tmp_path,
        views=[
            {
                "schema_version": 3,
                "id": "home",
                "text": {"inline": "Home"},
                "keyboard": [[{"id": "open_help", "text": "Help", "action": {"type": "view.render", "target": "help"}}]],
            },
            {
                "schema_version": 3,
                "id": "help",
                "text": {"inline": "Help"},
                "keyboard": [[
                    {"id": "begin_flow", "text": "Begin", "action": {"type": "flow.start", "target": "main"}},
                    {"id": "new_home", "text": "Home", "action": {"type": "view.render", "target": "home", "delivery": "send"}},
                ]],
            },
            {"schema_version": 3, "id": "ask", "text": {"inline": "Ask"}, "keyboard": []},
        ],
        flows=[{
            "schema_version": 3,
            "id": "main",
            "initial_state": "ask",
            "states": {"ask": {"view": "ask"}},
        }],
    )
    actor = Actor(41, 42)
    transport = FakeTransport()
    app = new_app(tmp_path, transport, [])
    await app.start()

    await transport.emit(CommandEvent(actor, 1, "unknown"))
    assert transport.messages[-1].edit_message_id is None

    await transport.emit(CallbackEvent(actor, 2, "open_help", message_id=501))
    assert (transport.messages[-1].text, transport.messages[-1].edit_message_id) == ("Help", 501)

    await transport.emit(CallbackEvent(actor, 3, "new_home", message_id=501))
    assert (transport.messages[-1].text, transport.messages[-1].edit_message_id) == ("Home", None)

    await transport.emit(CallbackEvent(actor, 4, "open_help", message_id=502))
    await transport.emit(CallbackEvent(actor, 5, "begin_flow", message_id=502))
    assert (transport.messages[-1].text, transport.messages[-1].edit_message_id) == ("Ask", 502)
    await app.stop()


@pytest.mark.asyncio
async def test_standalone_project_runs_flow_across_restart_without_studio(tmp_path: Path) -> None:
    make_interactive_project(tmp_path)
    actor = Actor(7, 8, first_name="Ada")
    trace: list[str] = []
    first_transport = FakeTransport()
    first = new_app(tmp_path, first_transport, trace)

    await first.start()
    await first_transport.emit(CommandEvent(actor, 1, "start"))
    assert first_transport.messages[-1].text == "Ask True"
    assert trace == ["start", "enter:ask"]

    await first_transport.emit(CommandEvent(actor, 2, "help"))
    assert first_transport.messages[-1].text == "Help"
    assert trace == ["start", "enter:ask"]

    await first_transport.emit(MessageEvent(actor, 3, "Ada"))
    assert (first_transport.messages[-1].text, first_transport.messages[-1].edit_message_id) == ("Confirm Ada", None)
    assert [button.callback_data for button in first_transport.messages[-1].keyboard[0]] == [
        "v3:a:confirm_order",
        "v3:a:cancel_order",
    ]
    session = await first.store.load_session("fixture-bot", actor)
    assert (session.status, session.flow_id, session.state_id, session.view_id) == (
        "active",
        "main",
        "confirm",
        "confirm",
    )
    assert session.variables == {"started": True, "state_only": "kept", "answer": "Ada"}
    await first.stop()

    second_transport = FakeTransport()
    restarted = new_app(tmp_path, second_transport, trace)
    await restarted.start()
    await second_transport.emit(CallbackEvent(actor, 4, "confirm_order"))

    assert second_transport.messages[-1].text == "Done Ada"
    assert trace == ["start", "enter:ask", "message:Ada", "enter:confirm", "submit", "complete"]
    completed = await restarted.store.load_session("fixture-bot", actor)
    assert (completed.status, completed.flow_id, completed.state_id, completed.view_id) == (
        "finished",
        None,
        None,
        "done",
    )

    message_count = len(second_transport.messages)
    await second_transport.emit(CallbackEvent(actor, 4, "confirm_order"))
    assert len(second_transport.messages) == message_count
    assert trace.count("submit") == 1
    await restarted.stop()
    assert first_transport.stopped and second_transport.stopped


@pytest.mark.asyncio
async def test_command_and_message_fallbacks_and_active_flow_dispatch_order(tmp_path: Path) -> None:
    make_interactive_project(tmp_path)
    actor = Actor(1, 2)
    trace: list[str] = []
    transport = FakeTransport()
    app = new_app(tmp_path, transport, trace)
    await app.start()

    await transport.emit(CommandEvent(actor, 1, "help"))
    assert transport.messages[-1].text == "Help"
    await transport.emit(CommandEvent(actor, 2, "unknown"))
    assert transport.messages[-1].text == "Command fallback"
    await transport.emit(MessageEvent(actor, 3, "idle text"))
    assert transport.messages[-1].text == "Message fallback"
    assert trace == ["fallback:command", "fallback:message"]

    await transport.emit(CommandEvent(actor, 4, "begin"))
    await transport.emit(MessageEvent(actor, 5, "inside flow"))
    assert transport.messages[-1].text == "Confirm inside flow"
    assert trace[-2:] == ["message:inside flow", "enter:confirm"]
    assert trace.count("fallback:message") == 1

    previous_trace = list(trace)
    await transport.emit(CallbackEvent(actor, 6, "stale_action"))
    assert transport.messages[-1].text == "Confirm inside flow"
    assert trace == previous_trace

    await transport.emit(CallbackEvent(actor, 7, "begin_main"))
    assert transport.messages[-1].text == "Confirm inside flow"
    assert trace == previous_trace
    await app.stop()


@pytest.mark.asyncio
async def test_invalid_outcome_rerenders_without_enter_and_cancel_runs_distinct_lifecycle(tmp_path: Path) -> None:
    make_interactive_project(tmp_path)
    actor = Actor(3, 4)
    trace: list[str] = []
    transport = FakeTransport()
    app = new_app(tmp_path, transport, trace)
    await app.start()

    await transport.emit(CommandEvent(actor, 1, "start"))
    await transport.emit(MessageEvent(actor, 2, "invalid"))
    assert transport.messages[-1].text == "Ask True"
    assert trace.count("enter:ask") == 1

    await transport.emit(MessageEvent(actor, 3, "valid"))
    await transport.emit(CallbackEvent(actor, 4, "cancel_order"))
    assert transport.messages[-1].text == "Cancelled"
    assert trace[-1] == "cancel"
    assert "complete" not in trace
    session = await app.store.load_session("fixture-bot", actor)
    assert session.status == "cancelled"
    await app.stop()


@pytest.mark.asyncio
async def test_handler_contract_error_runs_flow_on_error_hook(tmp_path: Path) -> None:
    make_interactive_project(tmp_path)
    actor = Actor(5, 6)
    trace: list[str] = []
    transport = FakeTransport()
    app = new_app(tmp_path, transport, trace)
    await app.start()

    await transport.emit(CommandEvent(actor, 1, "start"))
    await transport.emit(MessageEvent(actor, 2, "explode"))

    assert transport.messages[-1].text == "Handled error"
    assert any(item.startswith("error:Handler 'profile.save' returned NoneType") for item in trace)
    session = await app.store.load_session("fixture-bot", actor)
    assert session.status == "failed"
    assert session.view_id == "error"
    await app.stop()


@pytest.mark.asyncio
async def test_render_error_runs_flow_on_error_hook(tmp_path: Path) -> None:
    make_interactive_project(tmp_path)
    actor = Actor(17, 18)
    trace: list[str] = []
    transport = FakeTransport()
    app = new_app(tmp_path, transport, trace)
    await app.start()

    await transport.emit(CommandEvent(actor, 1, "start"))
    await transport.emit(MessageEvent(actor, 2, "broken"))

    assert transport.messages[-1].text == "Handled error"
    assert any(item.startswith("error:Failed to render view 'broken'") for item in trace)
    session = await app.store.load_session("fixture-bot", actor)
    assert session.status == "failed"
    assert session.view_id == "error"
    await app.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize(("policy", "expected_hooks"), [("reset", 2), ("resume", 1)])
async def test_start_policy_resets_or_resumes_existing_session(
    tmp_path: Path, policy: str, expected_hooks: int
) -> None:
    make_interactive_project(tmp_path, start_policy=policy)
    actor = Actor(9, 10)
    trace: list[str] = []
    transport = FakeTransport()
    app = new_app(tmp_path, transport, trace)
    await app.start()

    await transport.emit(CommandEvent(actor, 1, "start"))
    await transport.emit(CommandEvent(actor, 2, "start"))

    assert trace.count("start") == expected_hooks
    assert trace.count("enter:ask") == expected_hooks
    assert transport.messages[-1].text == "Ask True"
    await app.stop()


@pytest.mark.asyncio
async def test_session_conflict_is_retried_with_fresh_session(tmp_path: Path) -> None:
    make_interactive_project(tmp_path)
    actor = Actor(11, 12)
    trace: list[str] = []
    transport = FakeTransport()
    app = new_app(tmp_path, transport, trace)
    await app.start()
    assert app.dispatcher is not None
    original_dispatch = app.dispatcher.dispatch
    calls = 0

    async def conflict_once(session, event):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise SessionConflict("simulated")
        await original_dispatch(session, event)

    app.dispatcher.dispatch = conflict_once  # type: ignore[method-assign]
    await transport.emit(CommandEvent(actor, 1, "start"))

    assert calls == 2
    assert transport.messages[-1].text == "Ask True"
    await app.stop()


@pytest.mark.asyncio
async def test_automatic_transition_limit_fails_flow_instead_of_looping(tmp_path: Path) -> None:
    views = [{"schema_version": 3, "id": "home", "text": {"inline": "Home"}, "keyboard": []}]
    handlers = [
        {
            "id": "loop.enter",
            "module": "fixture_bot.handlers.loop_enter",
            "symbol": "handle",
            "kind": "lifecycle",
        }
    ]
    flows = [
        {
            "schema_version": 3,
            "id": "main",
            "initial_state": "loop",
            "states": {
                "loop": {
                    "view": "home",
                    "on_enter": {
                        "handler": "loop.enter",
                        "outcomes": {"success": {"type": "flow.goto", "target": "loop"}},
                    },
                }
            },
        }
    ]
    make_project(tmp_path, views=views, flows=flows, handlers=handlers)
    write_handler(
        tmp_path,
        "fixture_bot.handlers.loop_enter",
        """from tg_bot_core import HandlerResult, LifecycleContext
async def handle(ctx: LifecycleContext) -> HandlerResult:
    ctx.services["trace"].append("enter")
    return HandlerResult.success()
""",
    )
    trace: list[str] = []
    transport = FakeTransport()
    app = new_app(tmp_path, transport, trace, max_auto_transitions=4)
    actor = Actor(13, 14)
    await app.start()

    await transport.emit(CommandEvent(actor, 1, "start"))

    assert trace == ["enter", "enter"]
    assert transport.messages[-1].text == "The bot could not complete that action."
    session = await app.store.load_session("fixture-bot", actor)
    assert session.status == "failed"
    await app.stop()


@pytest.mark.asyncio
async def test_task_enqueue_persists_its_rendered_view(tmp_path: Path) -> None:
    views = [
        {
            "schema_version": 3,
            "id": "home",
            "text": {"inline": "Home"},
            "keyboard": [[
                {
                    "id": "queue_task",
                    "text": "Queue",
                    "action": {
                        "type": "task.enqueue",
                        "target": "tasks.run",
                        "view": "queued",
                    },
                }
            ]],
        },
        {
            "schema_version": 3,
            "id": "queued",
            "text": {"inline": "Queued"},
            "keyboard": [],
        },
    ]
    handlers = [
        {
            "id": "tasks.run",
            "module": "fixture_bot.handlers.task_run",
            "symbol": "handle",
            "kind": "task",
        }
    ]
    make_project(tmp_path, views=views, handlers=handlers)
    write_handler(
        tmp_path,
        "fixture_bot.handlers.task_run",
        "from tg_bot_core import HandlerResult, TaskContext\n\n"
        "async def handle(ctx: TaskContext) -> HandlerResult:\n"
        "    return HandlerResult.success()\n",
    )
    actor = Actor(15, 16)
    transport = FakeTransport()
    app = new_app(tmp_path, transport, [])
    await app.start()

    await transport.emit(CommandEvent(actor, 1, "start"))
    await transport.emit(CallbackEvent(actor, 2, "queue_task"))

    assert transport.messages[-1].text == "Queued"
    session = await app.store.load_session("fixture-bot", actor)
    assert session.view_id == "queued"
    await app.stop()


@pytest.mark.asyncio
async def test_run_async_handles_process_stop_signal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_project(tmp_path)
    transport = FakeTransport()
    app = new_app(tmp_path, transport, [])
    loop = asyncio.get_running_loop()
    callbacks: dict[signal.Signals, object] = {}
    removed: list[signal.Signals] = []

    def add_handler(signum, callback, *args):
        callbacks[signum] = lambda: callback(*args)

    monkeypatch.setattr(loop, "add_signal_handler", add_handler)
    monkeypatch.setattr(
        loop,
        "remove_signal_handler",
        lambda signum: removed.append(signum) or True,
    )

    running = asyncio.create_task(app.run_async())
    for _ in range(100):
        if transport.handler is not None:
            break
        await asyncio.sleep(0.01)
    assert transport.handler is not None
    callback = callbacks[signal.SIGTERM]
    assert callable(callback)
    callback()
    await asyncio.wait_for(running, timeout=2)

    assert transport.stopped
    assert signal.SIGINT in removed
    assert signal.SIGTERM in removed
