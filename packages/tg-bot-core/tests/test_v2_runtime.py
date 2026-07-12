from __future__ import annotations

from pathlib import Path

import pytest

from tg_bot_core import BotApp, BotConfig, BotModule, CommandEvent, FlowDefinition, FlowState, MessageEvent, Transition
from tg_bot_core.v2.events import Actor
from tg_bot_core.v2.jobs import DurableJobQueue
from tg_bot_core.v2.resources import CallbackCodec, ResourceError, ViewAction
from tg_bot_core.v2.store import SqliteStore
from tg_bot_core.v2.transport import BotTransport, EventHandler, OutboundMessage


class FakeTransport(BotTransport):
    def __init__(self) -> None:
        self.handler: EventHandler | None = None
        self.messages: list[OutboundMessage] = []

    async def start(self, handler: EventHandler) -> None:
        self.handler = handler

    async def stop(self) -> None:
        return

    async def send(self, message: OutboundMessage) -> None:
        self.messages.append(message)


class FailingTransport(FakeTransport):
    def __init__(self) -> None:
        super().__init__()
        self.stopped = False

    async def start(self, handler: EventHandler) -> None:
        raise RuntimeError("transport unavailable")

    async def stop(self) -> None:
        self.stopped = True


def make_resources(root: Path) -> None:
    (root / "views").mkdir(parents=True)
    (root / "templates").mkdir()
    (root / "bot.json").write_text('{"schema_version": 2, "entry_view": "home", "start_flow": "wizard"}', encoding="utf-8")
    (root / "views" / "home.json").write_text('{"schema_version": 2, "id": "home", "text": {"inline": "Home"}, "keyboard": []}', encoding="utf-8")
    (root / "views" / "done.json").write_text('{"schema_version": 2, "id": "done", "text": {"inline": "Done {{ answer }}"}, "keyboard": []}', encoding="utf-8")


@pytest.mark.asyncio
async def test_flow_state_is_persisted_and_recovered_after_restart(tmp_path: Path) -> None:
    resources = tmp_path / "resources"
    make_resources(resources)

    async def enter(ctx, event):
        return Transition.render("home")

    async def receive(ctx, event):
        ctx.set("answer", event.text)
        return Transition.finish(view="done")

    flow = FlowDefinition("wizard", "ask", {"ask": FlowState("ask", on_enter=enter, on_message=receive)})
    config = BotConfig("test", None, resources, tmp_path / "runtime.sqlite3")
    first_transport = FakeTransport()
    app = BotApp(config=config, module=BotModule(flows=[flow]), transport=first_transport)
    actor = Actor(7, 8, first_name="Ada")

    await app.start()
    await app.handle_event(CommandEvent(actor, 1, "start"))
    assert first_transport.messages[-1].text == "Home"
    await app.stop()

    second_transport = FakeTransport()
    restarted = BotApp(config=config, module=BotModule(flows=[flow]), transport=second_transport)
    await restarted.start()
    await restarted.handle_event(MessageEvent(actor, 2, "42"))
    assert second_transport.messages[-1].text == "Done 42"
    session = await restarted.store.load_session("test", actor)
    assert session.status == "finished"
    await restarted.stop()


@pytest.mark.asyncio
async def test_duplicate_update_is_not_processed_twice(tmp_path: Path) -> None:
    resources = tmp_path / "resources"
    make_resources(resources)
    calls = 0

    async def enter(ctx, event):
        nonlocal calls
        calls += 1
        return Transition.render("home")

    flow = FlowDefinition("wizard", "ask", {"ask": FlowState("ask", on_enter=enter)})
    app = BotApp(config=BotConfig("test", None, resources, tmp_path / "runtime.sqlite3"), module=BotModule(flows=[flow]), transport=FakeTransport())
    event = CommandEvent(Actor(1, 1), 99, "start")
    await app.start()
    await app.handle_event(event)
    await app.handle_event(event)
    assert calls == 1
    await app.stop()


@pytest.mark.asyncio
async def test_durable_queue_claims_and_retries_jobs(tmp_path: Path) -> None:
    store = SqliteStore(tmp_path / "jobs.sqlite3")
    await store.initialize()
    queue = DurableJobQueue(store, retry_base_seconds=0)
    job_id = await queue.enqueue("test", {"value": 1}, max_attempts=2)
    job = await queue.claim()
    assert job is not None and job.id == job_id
    await queue.fail(job, RuntimeError("temporary"))
    retried = await queue.claim()
    assert retried is not None and retried.id == job_id and retried.attempts == 1
    await queue.complete(retried)


def test_callback_codec_owns_v2_callback_protocol() -> None:
    codec = CallbackCodec()
    encoded = codec.encode(ViewAction("flow.start", "onboarding"))
    assert encoded == "v2:s:onboarding"
    assert codec.decode(encoded) == ViewAction("flow.start", "onboarding")
    with pytest.raises(ResourceError):
        codec.encode(ViewAction("navigate", "x" * 100))


@pytest.mark.asyncio
async def test_startup_failure_runs_reverse_transport_shutdown(tmp_path: Path) -> None:
    resources = tmp_path / "resources"
    make_resources(resources)
    flow = FlowDefinition("wizard", "ask", {"ask": FlowState("ask")})
    transport = FailingTransport()
    app = BotApp(config=BotConfig("test", None, resources, tmp_path / "runtime.sqlite3"), module=BotModule(flows=[flow]), transport=transport)
    with pytest.raises(RuntimeError, match="transport unavailable"):
        await app.start()
    assert transport.stopped
