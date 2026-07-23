from __future__ import annotations

import importlib
import inspect
import logging
import re
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from time import perf_counter
from types import MappingProxyType
from typing import Any

from .analytics import AnalyticsEventType, AnalyticsRecorder
from .events import Actor
from .project import HandlerBinding
from .sdk import HandlerResult

log = logging.getLogger(__name__)


class HandlerResolutionError(RuntimeError):
    pass


class HandlerExecutionError(RuntimeError):
    pass


class HandlerResolver:
    """Resolve only bindings explicitly declared in resources/handlers.json."""

    def __init__(self, bindings: Mapping[str, HandlerBinding], project_root: Path, package: str) -> None:
        self._bindings = dict(bindings)
        self._cache: dict[str, Callable[..., Any]] = {}
        self._source_root = (project_root / "src").resolve()
        self._package = package
        source_root = str(self._source_root)
        if source_root not in sys.path:
            sys.path.insert(0, source_root)

    def binding(self, handler_id: str) -> HandlerBinding:
        try:
            return self._bindings[handler_id]
        except KeyError as error:
            raise HandlerResolutionError(f"Handler binding '{handler_id}' does not exist.") from error

    def resolve(self, handler_id: str) -> Callable[..., Any]:
        cached = self._cache.get(handler_id)
        if cached is not None:
            return cached
        binding = self.binding(handler_id)
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*", binding.module):
            raise HandlerResolutionError(f"Handler '{handler_id}' has an invalid module path.")
        if not binding.module.startswith(f"{self._package}."):
            raise HandlerResolutionError(f"Handler '{handler_id}' is outside project package '{self._package}'.")
        source_file = self._source_root.joinpath(*binding.module.split(".")).with_suffix(".py").resolve(strict=False)
        if not source_file.is_relative_to(self._source_root) or not source_file.is_file():
            raise HandlerResolutionError(f"Handler module file does not exist inside project: {source_file}")
        self._evict_foreign_project_modules()
        try:
            module = importlib.import_module(binding.module)
        except Exception as error:
            raise HandlerResolutionError(f"Cannot import handler module '{binding.module}': {error}") from error
        try:
            handler = getattr(module, binding.symbol)
        except AttributeError as error:
            raise HandlerResolutionError(f"Handler symbol '{binding.module}:{binding.symbol}' does not exist.") from error
        if not callable(handler) or not inspect.iscoroutinefunction(handler):
            raise HandlerResolutionError(f"Handler '{handler_id}' must be an async callable.")
        signature = inspect.signature(handler)
        if len(signature.parameters) != 1:
            raise HandlerResolutionError(f"Handler '{handler_id}' must accept exactly one context argument.")
        self._cache[handler_id] = handler
        return handler

    def _evict_foreign_project_modules(self) -> None:
        """Avoid stale same-named packages in sequential in-process project runs."""
        for name, module in list(sys.modules.items()):
            if name != self._package and not name.startswith(f"{self._package}."):
                continue
            module_file = getattr(module, "__file__", None)
            if module_file and not Path(module_file).resolve().is_relative_to(self._source_root):
                sys.modules.pop(name, None)

    def validate_all(self) -> None:
        for handler_id in self._bindings:
            self.resolve(handler_id)


class HandlerExecutor:
    def __init__(
        self,
        resolver: HandlerResolver,
        services: Mapping[str, Any] | None = None,
        analytics: AnalyticsRecorder | None = None,
    ) -> None:
        self._resolver = resolver
        self.services: Mapping[str, Any] = MappingProxyType(dict(services or {}))
        self._analytics = analytics

    async def execute(
        self,
        handler_id: str,
        expected_kind: str,
        context: Any,
        *,
        metadata: Mapping[str, Any] | None = None,
        actor: Actor | None = None,
    ) -> HandlerResult:
        binding = self._resolver.binding(handler_id)
        if binding.kind != expected_kind:
            raise HandlerExecutionError(
                f"Handler '{handler_id}' has kind '{binding.kind}', not '{expected_kind}'."
            )
        handler = self._resolver.resolve(handler_id)
        contextual = {
            "handler_id": handler_id,
            "handler_kind": expected_kind,
            "user_id": getattr(getattr(context, "user", None), "id", None),
            "chat_id": getattr(getattr(context, "chat", None), "id", None),
            **dict(metadata or {}),
        }
        log.info("Invoking custom handler", extra=contextual)
        started_at = perf_counter()
        await self._record_handler_event(
            AnalyticsEventType.HANDLER_STARTED,
            handler_id=handler_id,
            expected_kind=expected_kind,
            actor=actor,
            execution_metadata=metadata,
        )
        try:
            result = await handler(context)
            if not isinstance(result, HandlerResult):
                raise HandlerExecutionError(
                    f"Handler '{handler_id}' returned {type(result).__name__}; expected HandlerResult."
                )
            allowed = {"success", *binding.outcomes}
            if result.outcome_name not in allowed:
                raise HandlerExecutionError(
                    f"Handler '{handler_id}' returned unknown outcome '{result.outcome_name}'."
                )
        except Exception as error:
            await self._record_handler_event(
                AnalyticsEventType.HANDLER_FAILED,
                handler_id=handler_id,
                expected_kind=expected_kind,
                actor=actor,
                execution_metadata=metadata,
                duration_ms=(perf_counter() - started_at) * 1000,
                error_type=type(error).__name__,
            )
            if isinstance(error, HandlerExecutionError):
                raise
            raise HandlerExecutionError(f"Handler '{handler_id}' failed: {error}") from error
        await self._record_handler_event(
            AnalyticsEventType.HANDLER_SUCCEEDED,
            handler_id=handler_id,
            expected_kind=expected_kind,
            actor=actor,
            execution_metadata=metadata,
            duration_ms=(perf_counter() - started_at) * 1000,
            outcome=result.outcome_name,
        )
        return result

    async def _record_handler_event(
        self,
        event_type: AnalyticsEventType,
        *,
        handler_id: str,
        expected_kind: str,
        actor: Actor | None,
        execution_metadata: Mapping[str, Any] | None,
        duration_ms: float | None = None,
        error_type: str | None = None,
        outcome: str | None = None,
    ) -> None:
        if self._analytics is None:
            return
        context = execution_metadata or {}
        analytics_metadata: dict[str, Any] = {"handler_kind": expected_kind}
        job_id = context.get("job_id")
        if isinstance(job_id, str) and job_id:
            analytics_metadata["job_id"] = job_id
        if duration_ms is not None:
            analytics_metadata["duration_ms"] = duration_ms
        if error_type is not None:
            analytics_metadata["error_type"] = error_type
        await self._analytics.record(
            event_type,
            actor=actor,
            handler_id=handler_id,
            flow_id=_optional_string(context.get("flow_id")),
            state_id=_optional_string(context.get("state_id")),
            view_id=_optional_string(context.get("view_id")),
            outcome=outcome,
            metadata=analytics_metadata,
        )


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None
