from __future__ import annotations

import logging
import os

from sqlalchemy.ext.asyncio import AsyncSession

from core.background.handler_registry import TaskPayload, background_task_handler
from pipubot.domains.tutoring.calendar.source_repository import (
    mark_reauth_required,
)
from pipubot.domains.tutoring.calendar.oauth_service import (
    GoogleOAuthReauthRequiredError,
)
from pipubot.domains.tutoring.lessons.services.preparation_service import (
    prepare_upcoming_lessons_for_delivery,
)
from pipubot.runtime.pipubot_services import PipubotServices
logger = logging.getLogger(__name__)


class PrepareLessonsPayload(TaskPayload):
    """
    Background task payload for upcoming lesson resource preparation.
    """

    tutor_user_id: int
    oauth_profile: str

    lookahead_minutes: int
    miro_lookahead_minutes: int
    limit: int

    http_timeout_s: float


@background_task_handler(
    recurring_key="system.prepare_lessons.konstantin",
    recurring_interval_seconds=180,
    recurring_payload_template={
        "tutor_user_id": int(os.environ["KONSTANTIN_USER_ID"]),
        "oauth_profile": "KONSTANTIN",
        "lookahead_minutes": 24 * 60,
        "miro_lookahead_minutes": 15,
        "limit": 200,
        "http_timeout_s": 20.0,
    },
)
async def prepare_lessons(
    session: AsyncSession,
    payload: PrepareLessonsPayload,
    services: PipubotServices,
) -> None:
    """
    Prepare runtime resources for upcoming lessons.

    Flow:
    1. Resolve calendar_id for the configured OAuth profile
    2. Build GoogleCalendarClient via runtime services
    3. Prepare upcoming lessons:
       - Meet links in the broad lookahead window
       - Miro boards in a short pre-lesson window
    """

    timeout_s = float(payload.get("http_timeout_s", 20.0))
    profile = payload["oauth_profile"]
    tutor_user_id = int(payload["tutor_user_id"])
    lookahead_minutes = int(payload.get("lookahead_minutes", 24 * 60))
    miro_lookahead_minutes = int(payload.get("miro_lookahead_minutes", 15))
    limit = int(payload.get("limit", 200))

    calendar_id = services.google_calendar.get_calendar_id(profile)

    try:
        client = await services.google_calendar.build_client(
            profile=profile,
            timeout_s=timeout_s,
        )
    except GoogleOAuthReauthRequiredError:
        logger.warning(
            "[prepare_lessons] reauth required tutor_user_id=%s calendar_id=%s profile=%s",
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

    await prepare_upcoming_lessons_for_delivery(
        session=session,
        tutor_user_id=tutor_user_id,
        client=client,
        lookahead_minutes=lookahead_minutes,
        miro_lookahead_minutes=miro_lookahead_minutes,
        limit=limit,
    )