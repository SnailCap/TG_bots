from __future__ import annotations

import asyncio
import importlib.util
import inspect
import logging
import sys
import traceback
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any, Protocol

from app.domain.project import BotProject
from app.domain.runtime import RuntimeResult
from app.domain.scripting import ActionParameter, ScriptAction
from app.domain.session import Session
from app.project_imports import isolated_project_imports
from app.sdk import (
    ActionBot,
    ActionChat,
    ActionContext,
    ActionRegistry,
    ActionResult,
    ActionUser,
    get_action_name,
)

from .errors import (
    ActionDiscoveryError,
    ActionExecutionError,
    ActionNotFoundError,
    ActionTimeoutError,
    InvalidActionResultError,
    RuntimeErrorContext,
)
from .events import RuntimeEventSink
from .transport import IncomingUpdate, TelegramPort

log = logging.getLogger("botstudio.actions")


class ActionInvoker(Protocol):
    async def invoke(
        self,
        *,
        project: BotProject,
        project_root: Path,
        session: Session,
        update: IncomingUpdate | None,
        action_name: str,
        timeout_seconds: float,
        parameters: dict[str, Any] | None = None,
        flow_id: str | None = None,
        node_id: str | None = None,
    ) -> RuntimeResult: ...


class ProjectActionLoader:
    """Discover decorated functions in one project's scripts directory."""

    def __init__(self) -> None:
        self._registries: dict[str, ActionRegistry] = {}
        self._descriptors: dict[str, tuple[ScriptAction, ...]] = {}
        self._signatures: dict[str, tuple[tuple[str, int, int], ...]] = {}

    def invalidate(self, project_id: str) -> None:
        self._registries.pop(project_id, None)
        self._descriptors.pop(project_id, None)
        self._signatures.pop(project_id, None)

    def registry(self, project_id: str, project_root: Path) -> ActionRegistry:
        files = self._script_files(project_root)
        signature = tuple(
            (str(path), path.stat().st_mtime_ns, path.stat().st_size) for path in files
        )
        if project_id not in self._registries or self._signatures.get(project_id) != signature:
            self._load(project_id, project_root, files, signature)
        return self._registries[project_id]

    def list_actions(self, project_id: str, project_root: Path) -> tuple[ScriptAction, ...]:
        self.registry(project_id, project_root)
        return self._descriptors.get(project_id, ())

    @staticmethod
    def _script_files(project_root: Path) -> tuple[Path, ...]:
        scripts = (project_root / "scripts").resolve()
        if not scripts.exists():
            return ()
        return tuple(
            path
            for path in sorted(scripts.rglob("*.py"))
            if "__pycache__" not in path.parts
        )

    def _load(
        self,
        project_id: str,
        project_root: Path,
        files: tuple[Path, ...],
        signature: tuple[tuple[str, int, int], ...],
    ) -> None:
        registry = ActionRegistry()
        descriptors: list[ScriptAction] = []
        for index, path in enumerate(files):
            module = self._load_module(project_id, project_root, path, index)
            for _, function in inspect.getmembers(module, inspect.isfunction):
                if function.__module__ != module.__name__:
                    continue
                action_name = get_action_name(function)
                if action_name is None:
                    continue
                self._validate_signature(action_name, function, path)
                line = inspect.getsourcelines(function)[1]
                try:
                    relative_path = path.relative_to(project_root).as_posix()
                    registry.register(
                        function,
                        module=module.__name__,
                        file_path=relative_path,
                        line=line,
                    )
                except ValueError as exc:
                    raise ActionDiscoveryError(str(exc)) from exc
                descriptors.append(
                    ScriptAction(
                        name=action_name,
                        module=module.__name__,
                        file_path=relative_path,
                        line=line,
                        is_async=inspect.iscoroutinefunction(function),
                        parameters=tuple(
                            ActionParameter(
                                name=parameter.name,
                                annotation=self._annotation_name(parameter.annotation),
                                required=parameter.default is inspect.Parameter.empty,
                            )
                            for parameter in inspect.signature(function).parameters.values()
                        ),
                        docstring=inspect.getdoc(function),
                    )
                )
        self._registries[project_id] = registry
        self._descriptors[project_id] = tuple(sorted(descriptors, key=lambda item: item.name))
        self._signatures[project_id] = signature

    @staticmethod
    def _load_module(
        project_id: str,
        project_root: Path,
        path: Path,
        index: int,
    ) -> ModuleType:
        safe_project = "".join(ch if ch.isalnum() else "_" for ch in project_id)
        module_name = f"_botstudio_project_{safe_project}_{index}_{path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ActionDiscoveryError(f"Cannot load script module: {path}")
        module = importlib.util.module_from_spec(spec)
        scripts_root = (project_root / "scripts").resolve()
        sys.modules[module_name] = module
        try:
            with isolated_project_imports(scripts_root):
                spec.loader.exec_module(module)
        except Exception as exc:
            sys.modules.pop(module_name, None)
            raise ActionDiscoveryError(
                f"Cannot import script '{path.relative_to(project_root)}': {exc}"
            ) from exc
        return module

    @staticmethod
    def _validate_signature(name: str, function: Any, path: Path) -> None:
        if not inspect.iscoroutinefunction(function):
            raise ActionDiscoveryError(
                f"Action '{name}' in {path} must be declared with async def"
            )
        parameters = list(inspect.signature(function).parameters.values())
        if len(parameters) != 1 or parameters[0].kind not in {
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        }:
            raise ActionDiscoveryError(
                f"Action '{name}' in {path} must accept exactly one ActionContext argument"
            )

    @staticmethod
    def _annotation_name(annotation: Any) -> str | None:
        if annotation is inspect.Parameter.empty:
            return None
        return getattr(annotation, "__name__", str(annotation))


class ProjectActionInvoker:
    def __init__(
        self,
        *,
        loader: ProjectActionLoader,
        telegram: TelegramPort,
        event_sink: RuntimeEventSink,
        storage: Any = None,
        services: Any = None,
    ) -> None:
        self._loader = loader
        self._telegram = telegram
        self._events = event_sink
        self._storage = storage
        self._services = services

    async def invoke(
        self,
        *,
        project: BotProject,
        project_root: Path,
        session: Session,
        update: IncomingUpdate | None,
        action_name: str,
        timeout_seconds: float,
        parameters: dict[str, Any] | None = None,
        flow_id: str | None = None,
        node_id: str | None = None,
    ) -> RuntimeResult:
        try:
            registered = self._loader.registry(project.id, project_root).require(action_name)
        except KeyError as exc:
            raise ActionNotFoundError(
                f"Unknown action '{action_name}'",
                context=RuntimeErrorContext(
                    project_id=project.id,
                    session_id=session.id,
                    details={"action": action_name},
                ),
            ) from exc

        variables = dict(session.variables)
        identity = project.configuration.identity
        context = ActionContext(
            project_id=project.id,
            session_id=session.id,
            user=ActionUser(
                id=session.telegram_user_id,
                username=update.username if update else None,
                first_name=update.first_name if update else None,
                last_name=update.last_name if update else None,
            ),
            chat=ActionChat(id=session.telegram_chat_id),
            bot=ActionBot(
                id=identity.bot_id if identity else 0,
                username=identity.username if identity else "",
                display_name=identity.display_name if identity else "",
            ),
            variables=variables,
            logger=log,
            parameters=dict(parameters or {}),
            services=self._services,
            telegram=self._telegram,
            storage=self._storage,
            metadata={
                "action_name": action_name,
                "flow_id": flow_id,
                "node_id": node_id,
            },
        )

        try:
            result = await asyncio.wait_for(
                self._call(registered.function, context),
                timeout=max(0.001, float(timeout_seconds)),
            )
        except asyncio.TimeoutError as exc:
            await self._emit_failure(
                project.id,
                session,
                action_name,
                f"Action timed out after {timeout_seconds:g}s",
                traceback.format_exc(),
                script_path=registered.file_path,
                line=registered.line,
                flow_id=flow_id,
                node_id=node_id,
            )
            raise ActionTimeoutError(
                f"Action '{action_name}' timed out after {timeout_seconds:g}s",
                context=RuntimeErrorContext(
                    project_id=project.id,
                    session_id=session.id,
                    details={"action": action_name, "timeout_seconds": timeout_seconds},
                ),
            ) from exc
        except Exception as exc:
            stack_trace = traceback.format_exc()
            await self._emit_failure(
                project.id,
                session,
                action_name,
                str(exc),
                stack_trace,
                script_path=registered.file_path,
                line=registered.line,
                flow_id=flow_id,
                node_id=node_id,
            )
            raise ActionExecutionError(
                f"Action '{action_name}' failed: {exc}",
                context=RuntimeErrorContext(
                    project_id=project.id,
                    session_id=session.id,
                    details={
                        "action": action_name,
                        "traceback": stack_trace,
                        "script_path": registered.file_path,
                        "line": registered.line,
                        "flow_id": flow_id,
                        "node_id": node_id,
                    },
                ),
            ) from exc

        if isinstance(result, ActionResult):
            runtime_result = result.to_runtime_result()
        elif isinstance(result, RuntimeResult):
            runtime_result = result
        else:
            message = (
                f"Action '{action_name}' returned {type(result).__name__}; "
                "expected ActionResult"
            )
            await self._emit_failure(
                project.id,
                session,
                action_name,
                message,
                "".join(traceback.format_stack()),
                script_path=registered.file_path,
                line=registered.line,
                flow_id=flow_id,
                node_id=node_id,
            )
            raise InvalidActionResultError(
                message,
                context=RuntimeErrorContext(
                    project_id=project.id,
                    session_id=session.id,
                    details={
                        "action": action_name,
                        "script_path": registered.file_path,
                        "line": registered.line,
                        "flow_id": flow_id,
                        "node_id": node_id,
                    },
                ),
            )

        changed_context = {
            key: value
            for key, value in context.variables.items()
            if key not in session.variables or session.variables[key] != value
        }
        merged_variables = dict(changed_context)
        merged_variables.update(runtime_result.variables)
        return replace(runtime_result, variables=merged_variables)

    @staticmethod
    async def _call(function: Any, context: ActionContext) -> Any:
        return await function(context)

    async def _emit_failure(
        self,
        project_id: str,
        session: Session,
        action_name: str,
        message: str,
        stack_trace: str,
        *,
        script_path: str | None = None,
        line: int | None = None,
        flow_id: str | None = None,
        node_id: str | None = None,
    ) -> None:
        await self._events.emit(
            "action.error",
            f"Action '{action_name}' failed: {message}",
            level="error",
            session_id=session.id,
            entity_type="action",
            entity_id=action_name,
            context={
                "traceback": stack_trace,
                "project_id": project_id,
                "script_path": script_path,
                "line": line,
                "flow_id": flow_id,
                "node_id": node_id,
            },
        )
