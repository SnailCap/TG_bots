from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.domain.ports.events import EventPublisher
from app.domain.ports.sessions import RuntimeStorage
from app.domain.runtime import RuntimeEvent, RuntimeHistoryEntry

log = logging.getLogger(__name__)


@dataclass(slots=True)
class RuntimeEventSink:
    project_id: str
    publisher: EventPublisher | None = None
    storage: RuntimeStorage | None = None

    async def emit(
        self,
        category: str,
        message: str,
        *,
        level: str = "info",
        session_id: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> RuntimeEvent:
        details = dict(context or {})
        if session_id is not None:
            details.setdefault("session_id", session_id)

        event = RuntimeEvent(
            project_id=self.project_id,
            category=category,
            message=message,
            level=level,
            context=details,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        if self.storage is not None:
            try:
                self.storage.append_history(
                    RuntimeHistoryEntry(
                        project_id=self.project_id,
                        event_type=category,
                        message=message,
                        level=level,
                        session_id=session_id,
                        context=details,
                    )
                )
            except Exception:
                log.exception("Failed to persist runtime history event")

        if self.publisher is not None:
            try:
                event = await self.publisher.publish(event)
            except Exception:
                log.exception("Failed to publish runtime event")
        return event

