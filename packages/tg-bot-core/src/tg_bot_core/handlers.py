from __future__ import annotations

import importlib
import inspect
import logging
import re
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any

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
    def __init__(self, resolver: HandlerResolver, services: Mapping[str, Any] | None = None) -> None:
        self._resolver = resolver
        self.services: Mapping[str, Any] = MappingProxyType(dict(services or {}))

    async def execute(
        self,
        handler_id: str,
        expected_kind: str,
        context: Any,
        *,
        metadata: Mapping[str, Any] | None = None,
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
        try:
            result = await handler(context)
        except Exception as error:
            raise HandlerExecutionError(f"Handler '{handler_id}' failed: {error}") from error
        if not isinstance(result, HandlerResult):
            raise HandlerExecutionError(
                f"Handler '{handler_id}' returned {type(result).__name__}; expected HandlerResult."
            )
        allowed = {"success", *binding.outcomes}
        if result.outcome_name not in allowed:
            raise HandlerExecutionError(
                f"Handler '{handler_id}' returned unknown outcome '{result.outcome_name}'."
            )
        return result
