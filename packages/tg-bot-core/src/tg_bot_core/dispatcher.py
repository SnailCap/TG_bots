from __future__ import annotations

import logging

from .catalog import CatalogError, ProjectCatalog
from .engine import FlowEngine
from .events import CallbackEvent, CommandEvent, InteractionEvent, MessageEvent
from .handlers import HandlerExecutionError
from .project import ProjectDefinition
from .store import FlowSession

log = logging.getLogger(__name__)


class EventDispatcher:
    """Apply the documented event precedence without owning flow mechanics."""

    def __init__(self, project: ProjectDefinition, catalog: ProjectCatalog, engine: FlowEngine) -> None:
        self.project = project
        self.catalog = catalog
        self.engine = engine

    async def dispatch(self, session: FlowSession, event: InteractionEvent) -> None:
        try:
            if isinstance(event, CommandEvent):
                await self._command(session, event)
                return
            if isinstance(event, CallbackEvent):
                action = self.catalog.action(
                    event.action_id,
                    current_view=self.engine.current_view(session),
                )
                if action is None:
                    log.warning(
                        "Ignoring stale or inactive callback action '%s'",
                        event.action_id,
                    )
                    await self.engine.render_current(session)
                else:
                    await self.engine.apply_action(session, action, event, "button")
                return
            if isinstance(event, MessageEvent):
                invocation = self.engine.active_message_handler(session)
                if invocation:
                    await self.engine.invoke_and_route(session, invocation, event, "message")
                    return
                if self.project.commands.message_fallback:
                    await self.engine.apply_action(session, self.project.commands.message_fallback, event, "message")
                    return
            await self.engine.render_current(session)
        except (HandlerExecutionError, CatalogError) as error:
            await self.engine.handle_error(session, event, error)

    async def _command(self, session: FlowSession, event: CommandEvent) -> None:
        command = event.command.lower().removeprefix("/")
        if command == "start":
            if self.project.manifest.start.policy == "resume" and session.status == "active":
                await self.engine.render_current(session)
            else:
                await self.engine.start_flow(session, self.project.manifest.start.flow, event)
            return
        spec = next((item for item in self.project.commands.commands if item.name.lower() == command), None)
        if spec:
            await self.engine.apply_action(session, spec.action, event, "command")
            return
        if self.project.commands.command_fallback:
            await self.engine.apply_action(session, self.project.commands.command_fallback, event, "command")
            return
        await self.engine.render_current(session)
