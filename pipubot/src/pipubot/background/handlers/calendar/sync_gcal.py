from __future__ import annotations

import os

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from core.background.handler_registry import task_handler
from core.runtime.app_services import AppServices
from pipubot.background.handlers.task_types import BackgroundTaskType
from pipubot.domains.tutoring.integrations.google_calendar.google_calendar_client import GoogleCalendarClient, \
    GoogleCalendarClientConfig
from pipubot.domains.tutoring.services.calendar.calendar_sync_service import sync_calendar


@task_handler(
    BackgroundTaskType.SYNC_GCAL,
    recurring_key="system.sync_gcal.konstantin",
    recurring_interval_seconds=60,
    recurring_payload_template={"tutor_user_id": int(os.environ["KONSTANTIN_USER_ID"])},
)
# @task_handler(
#     BackgroundTaskType.SYNC_GCAL,
#     recurring_key="system.sync_gcal.margarita",
#     recurring_interval_seconds=60,
#     recurring_payload_template={"tutor_user_id": 2},
# )
async def sync_gcal(session: AsyncSession, payload: dict, services: AppServices) -> None:
    tutor_user_id = int(payload["tutor_user_id"])
    calendar_id = os.environ.get("GCAL_CALENDAR_ID", "primary")
    tutor_user_id = int(os.environ["KONSTANTIN_USER_ID"])

    client_id = os.environ["GCAL_CLIENT_ID"]
    client_secret = os.environ["GCAL_CLIENT_SECRET"]
    refresh_token = os.environ["GCAL_REFRESH_TOKEN"]

    access_token = await _refresh_access_token(
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
    )

    client = GoogleCalendarClient(
        GoogleCalendarClientConfig(access_token=access_token)
    )

    await sync_calendar(
        session,
        tutor_user_id=tutor_user_id,
        calendar_id=calendar_id,
        client=client,
        horizon_days=60,
        backfill_days=7
    )

    print("Calendar sync finished successfully.")


async def _refresh_access_token(
        *,
        client_id: str,
        client_secret: str,
        refresh_token: str,
) -> str:
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["access_token"]
