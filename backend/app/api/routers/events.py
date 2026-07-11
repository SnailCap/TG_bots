from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from app.api.container import AppContainer
from app.api.dependencies import get_container
from app.infrastructure.json_codec import dumps_json

router = APIRouter(tags=["events"])


@router.get("/events")
async def events(
    request: Request,
    project_id: str | None = None,
    after_id: int = Query(default=0, ge=0),
    container: AppContainer = Depends(get_container),
) -> StreamingResponse:
    async def stream():
        last_id = after_id
        async with container.events.subscribe() as queue:
            for event in container.events.snapshot(
                project_id=project_id,
                after_id=last_id,
            ):
                last_id = max(last_id, event.id)
                yield _encode(event)
            while not await request.is_disconnected():
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                if event.id <= last_id:
                    continue
                if project_id is not None and event.project_id not in {None, project_id}:
                    continue
                last_id = event.id
                yield _encode(event)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/projects/{project_id}/runtime/events")
async def project_runtime_events(
    project_id: str,
    request: Request,
    after_id: int = Query(default=0, ge=0),
    container: AppContainer = Depends(get_container),
) -> StreamingResponse:
    return await events(
        request=request,
        project_id=project_id,
        after_id=after_id,
        container=container,
    )


def _encode(event) -> str:
    payload = {
        "id": event.id,
        "project_id": event.project_id,
        "category": event.category,
        "level": event.level,
        "message": event.message,
        "context": event.context,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
        "created_at": event.created_at.isoformat(),
    }
    return f"id: {event.id}\nevent: runtime\ndata: {dumps_json(payload)}\n\n"
