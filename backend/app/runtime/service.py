from __future__ import annotations

import asyncio
import traceback
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Awaitable, Callable, Protocol

from app.domain.enums import RuntimeState, ValidationSeverity
from app.domain.project import BotProject
from app.domain.runtime import BotRuntimeStatus
from app.domain.validation import ValidationIssue

from .errors import RuntimeValidationError
from .events import RuntimeEventSink
from .executor import GraphExecutor
from .transport import IncomingUpdate, TelegramPort
from .validation import RuntimeProjectValidator


class RuntimeService:
    """Lifecycle boundary for one bot project.

    It intentionally owns no PTB objects; a future worker proxy can implement the
    same start/stop/status surface while GraphExecutor remains unchanged.
    """

    def __init__(
        self,
        *,
        project: BotProject,
        project_root: Path,
        token: str,
        telegram: TelegramPort,
        executor: GraphExecutor,
        validator: RuntimeProjectValidator,
        events: RuntimeEventSink,
    ) -> None:
        self.project = project
        self.project_root = project_root.resolve()
        self._token = token
        self._telegram = telegram
        self._executor = executor
        self._validator = validator
        self._events = events
        self._status = BotRuntimeStatus(project_id=project.id)
        self._validation_issues: tuple[ValidationIssue, ...] = ()
        self._lifecycle_lock = asyncio.Lock()
        self._ready = asyncio.Event()

    @property
    def status(self) -> BotRuntimeStatus:
        return self._status

    @property
    def validation_issues(self) -> tuple[ValidationIssue, ...]:
        return self._validation_issues

    @property
    def is_ready(self) -> bool:
        return self._ready.is_set() and self._status.state is RuntimeState.RUNNING

    async def start(self) -> BotRuntimeStatus:
        async with self._lifecycle_lock:
            if self._status.state is RuntimeState.RUNNING:
                return self._status
            if self._status.state in {RuntimeState.STARTING, RuntimeState.STOPPING}:
                raise RuntimeError(
                    f"Cannot start runtime while it is {self._status.state.value}"
                )

            self._ready.clear()
            self._status = replace(
                self._status,
                state=RuntimeState.STARTING,
                last_error=None,
                stopped_at=None,
            )
            await self._events.emit("runtime.starting", "Bot runtime is starting")

            self._validation_issues = self._validator.validate(
                self.project,
                self.project_root,
                token=self._token,
            )
            critical = tuple(
                issue
                for issue in self._validation_issues
                if issue.severity is ValidationSeverity.ERROR
            )
            if critical:
                message = "; ".join(f"{issue.code}: {issue.message}" for issue in critical)
                self._status = replace(
                    self._status,
                    state=RuntimeState.ERROR,
                    last_error=message,
                )
                await self._events.emit(
                    "runtime.validation_failed",
                    message,
                    level="error",
                    context={
                        "issues": [
                            {
                                "code": issue.code,
                                "message": issue.message,
                                "entity_type": issue.entity_type,
                                "entity_id": issue.entity_id,
                            }
                            for issue in critical
                        ]
                    },
                )
                raise RuntimeValidationError(message)

            try:
                identity = await self._telegram.start(self._handle_update_safely)
            except Exception as exc:
                try:
                    await self._telegram.stop()
                except Exception:
                    pass
                self._status = replace(
                    self._status,
                    state=RuntimeState.ERROR,
                    last_error=str(exc),
                )
                await self._events.emit(
                    "runtime.start_failed",
                    str(exc),
                    level="error",
                    context={"traceback": traceback.format_exc()},
                )
                raise

            self._status = replace(
                self._status,
                state=RuntimeState.RUNNING,
                bot_identity=identity,
                started_at=datetime.now(UTC),
                stopped_at=None,
                last_error=None,
            )
            self._ready.set()
            await self._events.emit(
                "runtime.started",
                f"Bot runtime started as @{identity.username}",
                context={"bot_id": identity.bot_id, "username": identity.username},
            )
            return self._status

    async def stop(self) -> BotRuntimeStatus:
        async with self._lifecycle_lock:
            if self._status.state is RuntimeState.STOPPED:
                return self._status
            self._ready.clear()
            self._status = replace(self._status, state=RuntimeState.STOPPING)
            await self._events.emit("runtime.stopping", "Bot runtime is stopping")
            error: Exception | None = None
            try:
                await self._telegram.stop()
            except Exception as exc:
                error = exc
            self._status = replace(
                self._status,
                state=RuntimeState.ERROR if error else RuntimeState.STOPPED,
                stopped_at=datetime.now(UTC),
                last_error=str(error) if error else self._status.last_error,
            )
            await self._events.emit(
                "runtime.stop_failed" if error else "runtime.stopped",
                str(error) if error else "Bot runtime stopped",
                level="error" if error else "info",
            )
            if error is not None:
                raise error
            return self._status

    async def wait_until_ready(self, timeout: float | None = None) -> None:
        if timeout is None:
            await self._ready.wait()
        else:
            await asyncio.wait_for(self._ready.wait(), timeout=timeout)

    async def handle_update(self, update: IncomingUpdate) -> None:
        """Public seam used by fakes and a future worker receiver."""
        await self._handle_update_safely(update)

    async def _handle_update_safely(self, update: IncomingUpdate) -> None:
        if self._status.state is not RuntimeState.RUNNING:
            return
        try:
            await self._executor.handle_update(update)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # One malformed update or project action must not stop polling/backend.
            self._status = replace(self._status, last_error=str(exc))
            await self._events.emit(
                "update.failed",
                str(exc),
                level="error",
                context={
                    "update_id": update.update_id,
                    "telegram_user_id": update.telegram_user_id,
                    "telegram_chat_id": update.telegram_chat_id,
                    "traceback": traceback.format_exc(),
                },
            )


class RuntimeServiceFactory(Protocol):
    def __call__(
        self,
        project: BotProject,
        project_root: Path,
        token: str,
    ) -> RuntimeService: ...


class RuntimeManager:
    """Own and control many isolated bot runtimes in one backend process."""

    def __init__(self, factory: RuntimeServiceFactory) -> None:
        self._factory = factory
        self._services: dict[str, RuntimeService] = {}
        self._lock = asyncio.Lock()

    async def run(
        self,
        project: BotProject,
        project_root: Path,
        token: str,
    ) -> BotRuntimeStatus:
        async with self._lock:
            service = self._services.get(project.id)
            if service is None or service.status.state in {
                RuntimeState.ERROR,
                RuntimeState.STOPPED,
            }:
                service = self._factory(project, project_root, token)
                self._services[project.id] = service
        return await service.start()

    async def stop(self, project_id: str) -> BotRuntimeStatus:
        service = self._services.get(project_id)
        if service is None:
            return BotRuntimeStatus(
                state=RuntimeState.STOPPED,
                project_id=project_id,
            )
        return await service.stop()

    async def stop_all(self) -> None:
        services = tuple(self._services.values())
        if services:
            await asyncio.gather(
                *(service.stop() for service in services),
                return_exceptions=True,
            )

    def get(self, project_id: str) -> RuntimeService | None:
        return self._services.get(project_id)

    def status(self, project_id: str) -> BotRuntimeStatus:
        service = self._services.get(project_id)
        return (
            service.status
            if service is not None
            else BotRuntimeStatus(
                state=RuntimeState.STOPPED,
                project_id=project_id,
            )
        )

    def statuses(self) -> tuple[BotRuntimeStatus, ...]:
        return tuple(
            self._services[project_id].status
            for project_id in sorted(self._services)
        )

