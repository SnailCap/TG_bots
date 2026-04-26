from __future__ import annotations

import logging
import os
from time import perf_counter

from sqlalchemy.ext.asyncio import AsyncSession

from core.background.handler_registry import TaskPayload, background_task_handler
from pipubot.domains.tutoring.integrations.google_calendar.client import (
    GoogleCalendarClient,
    GoogleCalendarClientConfig,
)
from pipubot.domains.tutoring.calendar.source_repository import (
    mark_reauth_required,
)
from pipubot.domains.tutoring.calendar.sync_service import sync_calendar
from pipubot.domains.tutoring.calendar.oauth_service import (
    GoogleOAuthReauthRequiredError,
)
from pipubot.runtime.pipubot_services import PipubotServices
logger = logging.getLogger(__name__)


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
        services: PipubotServices,
) -> None:
    """
    Synchronize lessons with Google Calendar.

    Flow:
    1. Resolve OAuth credentials via SecretsService
    2. Refresh Google access token
    3. Create GoogleCalendarClient
    4. Run a domain sync service
    """

    started_at = perf_counter()

    timeout_s = float(payload.get("http_timeout_s", 20.0))
    profile = payload["oauth_profile"]
    tutor_user_id = payload["tutor_user_id"]

    # ------------------------------------------------------------------
    # Resolve OAuth config
    # ------------------------------------------------------------------

    oauth = services.secrets.google_calendar.get_oauth_profile(profile)
    calendar_id = services.secrets.google_calendar.get_calendar_id(profile)

    # ------------------------------------------------------------------
    # Refresh Google OAuth access token
    # ------------------------------------------------------------------

    try:
        access_token = await services.google_oauth.refresh_access_token(
            client_id=oauth.client_id,
            client_secret=oauth.client_secret,
            refresh_token=oauth.refresh_token,
            timeout_s=timeout_s,
        )
    except GoogleOAuthReauthRequiredError:
        logger.warning(
            "[sync_gcal] reauth required tutor_user_id=%s calendar_id=%s profile=%s",
            tutor_user_id,
            calendar_id,
            profile,
        )

        await mark_reauth_required(
            session,
            tutor_user_id=tutor_user_id,
            calendar_id=calendar_id,
        )
        return

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
    # Run domain sync
    # ------------------------------------------------------------------

    await sync_calendar(
        session=session,
        tutor_user_id=tutor_user_id,
        calendar_id=calendar_id,
        client=client,
        horizon_days=payload["horizon_days"],
        backfill_days=payload["backfill_days"],
    )

    elapsed_ms = int((perf_counter() - started_at) * 1000)

    logger.info(
        "[sync_gcal] completed tutor_user_id=%s calendar_id=%s profile=%s duration_ms=%s",
        tutor_user_id,
        calendar_id,
        profile,
        elapsed_ms,
    )
