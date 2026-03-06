from __future__ import annotations

import os

from sqlalchemy.ext.asyncio import AsyncSession

from core.background.handler_registry import background_task_handler, TaskPayload

from pipubot.domains.tutoring.integrations.google_calendar.google_calendar_client import (
    GoogleCalendarClient,
    GoogleCalendarClientConfig,
)
from pipubot.domains.tutoring.services.gcal.calendar_sync_service import sync_calendar
from pipubot.runtime.runtime_services import DefaultAppServices


class SyncGcalPayload(TaskPayload):
    """
    Background task payload for Google Calendar synchronization.
    """

    tutor_user_id: int
    oauth_profile: str

    horizon_days: int
    backfill_days: int

    http_timeout_s: float


@background_task_handler(
    recurring_key="system.sync_gcal.konstantin",
    recurring_interval_seconds=60,
    recurring_payload_template={
        "tutor_user_id": int(os.environ["KONSTANTIN_USER_ID"]),
        "oauth_profile": "KONSTANTIN",
        "horizon_days": 60,
        "backfill_days": 7,
        "http_timeout_s": 20.0,
    },
)
async def sync_gcal(
    session: AsyncSession,
    payload: SyncGcalPayload,
    services: DefaultAppServices,
) -> None:
    """
    Synchronize lessons with Google Calendar.

    Flow:
    1. Resolve OAuth credentials via SecretsService
    2. Refresh Google access token
    3. Create GoogleCalendarClient
    4. Run a domain sync service
    """

    timeout_s = float(payload.get("http_timeout_s", 20.0))
    profile = payload["oauth_profile"]

    # ------------------------------------------------------------------
    # Resolve OAuth credentials from SecretsService
    # ------------------------------------------------------------------

    oauth = services.secrets.google_calendar.get_oauth_profile(profile)

    # ------------------------------------------------------------------
    # Refresh Google OAuth access token
    # ------------------------------------------------------------------

    access_token = await services.google_oauth.refresh_access_token(
        client_id=oauth.client_id,
        client_secret=oauth.client_secret,
        refresh_token=oauth.refresh_token,
        timeout_s=timeout_s,
    )

    # ------------------------------------------------------------------
    # Build Google Calendar client
    # ------------------------------------------------------------------

    client = GoogleCalendarClient(
        GoogleCalendarClientConfig(
            access_token=access_token,
            timeout_s=timeout_s,
        )
    )

    # ------------------------------------------------------------------
    # Resolve calendar id
    # ------------------------------------------------------------------

    calendar_id = services.secrets.google_calendar.get_calendar_id(profile)

    # ------------------------------------------------------------------
    # Run domain sync
    # ------------------------------------------------------------------

    await sync_calendar(
        session=session,
        tutor_user_id=payload["tutor_user_id"],
        calendar_id=calendar_id,
        client=client,
        horizon_days=payload["horizon_days"],
        backfill_days=payload["backfill_days"],
    )

    print("Google Calendar sync finished successfully.")