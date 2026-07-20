from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from tg_bot_core import (
    Actor,
    ChatInfo,
    HandlerResult,
    MessageContext,
    MessageEvent,
    ServiceProvider,
    StateValues,
    UserInfo,
)
from tg_bot_core.handlers import (
    HandlerExecutionError,
    HandlerExecutor,
    HandlerResolutionError,
    HandlerResolver,
)
from tg_bot_core.project import HandlerBinding
from tg_bot_core.services import ServiceContainer

from conftest import make_project, write_handler


def binding(
    handler_id: str,
    module: str,
    *,
    kind: str = "message",
    outcomes: tuple[str, ...] = (),
) -> HandlerBinding:
    return HandlerBinding(handler_id, module, "handle", kind, outcomes)


def test_handler_result_is_immutable_and_requires_json_values() -> None:
    source = {"count": 1}
    result = HandlerResult.success(values=source)
    source["count"] = 2

    assert result.outcome_name == "success"
    assert result.values == {"count": 1}
    with pytest.raises(TypeError):
        result.values["count"] = 3  # type: ignore[index]
    with pytest.raises(ValueError):
        HandlerResult.outcome(" ")
    with pytest.raises(TypeError, match="JSON-serializable"):
        HandlerResult.success(values={"bad": object()})
    with pytest.raises(TypeError, match="non-string"):
        HandlerResult.success(values={1: "bad"})  # type: ignore[dict-item]
    with pytest.raises(TypeError, match="non-finite"):
        HandlerResult.success(values={"bad": float("nan")})


def test_context_mappings_are_read_only_and_state_uses_controlled_json_writes() -> None:
    original_payload = {"nested": {"enabled": True}}
    context = MessageContext(
        user=UserInfo(1),
        chat=ChatInfo(2),
        event=MessageEvent(Actor(1, 2), 3, "hello"),
        payload=original_payload,
        state=StateValues(),
        services={"api": object()},
        logger=logging.getLogger("test"),
    )

    with pytest.raises(TypeError):
        context.payload["new"] = True  # type: ignore[index]
    with pytest.raises(TypeError):
        context.payload["nested"]["enabled"] = False  # type: ignore[index]
    with pytest.raises(TypeError):
        context.services["new"] = object()  # type: ignore[index]
    assert original_payload == {"nested": {"enabled": True}}
    with pytest.raises(TypeError, match="non-empty string"):
        context.state.set("", 1)
    with pytest.raises(TypeError, match="non-finite"):
        context.state.set("bad", float("inf"))


def test_resolver_loads_only_explicit_project_modules_and_caches_callable(tmp_path: Path) -> None:
    make_project(tmp_path)
    write_handler(
        tmp_path,
        "fixture_bot.handlers.valid",
        "from tg_bot_core import HandlerResult\n\nasync def handle(ctx):\n    return HandlerResult.success()\n",
    )
    resolver = HandlerResolver(
        {"valid": binding("valid", "fixture_bot.handlers.valid")},
        tmp_path,
        "fixture_bot",
    )

    first = resolver.resolve("valid")
    second = resolver.resolve("valid")

    assert first is second
    with pytest.raises(HandlerResolutionError, match="does not exist"):
        resolver.resolve("undeclared")


@pytest.mark.parametrize(
    ("module", "source", "message"),
    [
        ("fixture_bot.handlers.missing", None, "does not exist inside project"),
        ("fixture_bot.handlers.symbol", "async def other(ctx):\n    return None\n", "symbol"),
        ("fixture_bot.handlers.sync", "def handle(ctx):\n    return None\n", "async callable"),
        ("fixture_bot.handlers.arity", "async def handle(one, two):\n    return None\n", "exactly one"),
        ("external.handlers.bad", "async def handle(ctx):\n    return None\n", "outside project package"),
        ("fixture_bot.handlers/escape", "async def handle(ctx):\n    return None\n", "invalid module path"),
    ],
)
def test_resolver_rejects_missing_or_invalid_binding_targets(
    tmp_path: Path, module: str, source: str | None, message: str
) -> None:
    make_project(tmp_path)
    if source is not None and "/" not in module and module.startswith("fixture_bot"):
        write_handler(tmp_path, module, source)
    resolver = HandlerResolver({"bad": binding("bad", module)}, tmp_path, "fixture_bot")

    with pytest.raises(HandlerResolutionError, match=message):
        resolver.resolve("bad")


@pytest.mark.asyncio
async def test_executor_validates_kind_result_outcome_and_handler_errors(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    make_project(tmp_path)
    modules = {
        "ok": "from tg_bot_core import HandlerResult\nasync def handle(ctx):\n    return HandlerResult.outcome('invalid', values={'seen': True})\n",
        "wrong_result": "async def handle(ctx):\n    return None\n",
        "unknown": "from tg_bot_core import HandlerResult\nasync def handle(ctx):\n    return HandlerResult.outcome('surprise')\n",
        "raises": "async def handle(ctx):\n    raise RuntimeError('boom')\n",
    }
    bindings: dict[str, HandlerBinding] = {}
    for name, source in modules.items():
        module = f"fixture_bot.handlers.{name}"
        write_handler(tmp_path, module, source)
        bindings[name] = binding(name, module, outcomes=("invalid",) if name == "ok" else ())
    executor = HandlerExecutor(HandlerResolver(bindings, tmp_path, "fixture_bot"), {"service": 42})
    context = SimpleNamespace(
        user=SimpleNamespace(id=1),
        chat=SimpleNamespace(id=2),
    )

    with caplog.at_level("INFO", logger="tg_bot_core.handlers"):
        result = await executor.execute(
            "ok",
            "message",
            context,
            metadata={"flow_id": "checkout", "state_id": "details"},
        )

    assert result.outcome_name == "invalid"
    assert result.values == {"seen": True}
    record = next(item for item in caplog.records if item.message == "Invoking custom handler")
    assert record.handler_id == "ok"
    assert record.handler_kind == "message"
    assert record.flow_id == "checkout"
    assert record.state_id == "details"
    assert record.user_id == 1
    assert record.chat_id == 2
    assert executor.services == {"service": 42}
    with pytest.raises(HandlerExecutionError, match="not 'command'"):
        await executor.execute("ok", "command", context)
    with pytest.raises(HandlerExecutionError, match="expected HandlerResult"):
        await executor.execute("wrong_result", "message", context)
    with pytest.raises(HandlerExecutionError, match="unknown outcome"):
        await executor.execute("unknown", "message", context)
    with pytest.raises(HandlerExecutionError, match="failed: boom"):
        await executor.execute("raises", "message", context)


@pytest.mark.asyncio
async def test_services_build_in_order_and_close_in_reverse_order() -> None:
    events: list[str] = []
    container = ServiceContainer()

    async def dispose_first(value) -> None:
        events.append(f"close:{value}")

    async def dispose_second(value) -> None:
        events.append(f"close:{value}")

    await container.build(
        [
            ServiceProvider("first", lambda _container: "first", dispose_first),
            ServiceProvider("second", lambda current: f"second-after-{current.get('first')}", dispose_second),
        ]
    )

    assert container.all() == {"first": "first", "second": "second-after-first"}
    await container.close()
    assert events == ["close:second-after-first", "close:first"]
    assert container.all() == {}


@pytest.mark.asyncio
async def test_service_async_context_and_partial_build_failure_are_cleaned_up() -> None:
    events: list[str] = []

    class Managed:
        async def __aenter__(self):
            events.append("enter")
            return "managed-value"

        async def __aexit__(self, exc_type, exc, traceback):
            events.append("exit")

    def fail(_container):
        raise RuntimeError("factory failed")

    container = ServiceContainer()
    with pytest.raises(RuntimeError, match="factory failed"):
        await container.build(
            [
                ServiceProvider("managed", lambda _container: Managed()),
                ServiceProvider("broken", fail),
            ]
        )

    assert events == ["enter", "exit"]
    assert container.all() == {}


@pytest.mark.asyncio
async def test_service_cleanup_attempts_every_disposer_even_when_multiple_fail() -> None:
    events: list[str] = []

    def failing_disposer(value) -> None:
        events.append(value)
        raise RuntimeError(value)

    container = ServiceContainer()
    await container.build(
        [
            ServiceProvider("first", lambda _container: "first", failing_disposer),
            ServiceProvider("second", lambda _container: "second", failing_disposer),
        ]
    )

    with pytest.raises(ExceptionGroup) as captured:
        await container.close()

    assert events == ["second", "first"]
    assert len(captured.value.exceptions) == 2
    assert container.all() == {}
