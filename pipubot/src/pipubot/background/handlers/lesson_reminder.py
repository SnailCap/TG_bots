from __future__ import annotations

import logging
import os

from sqlalchemy.ext.asyncio import AsyncSession

from core.background.handler_registry import background_task_handler, TaskPayload
from pipubot.domains.tutoring.calendar.oauth_service import (
    GoogleOAuthReauthRequiredError,
)
from pipubot.domains.tutoring.lessons.contracts.queries import LessonReminderCandidate
from pipubot.domains.tutoring.lessons.services.meet_link_service import (
    ensure_lesson_meet_link,
)
from pipubot.domains.tutoring.lessons.services.reminder_service import (
    build_upcoming_lesson_reminder_candidates,
)
from pipubot.runtime.pipubot_services import PipubotServices

logger = logging.getLogger(__name__)


class LessonReminderPayload(TaskPayload):
    tutor_user_id: int
    notify_before_minutes: int


def _stringify_status(value: object) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _build_notification_text_vars(
    lesson: LessonReminderCandidate,
    meet_url: str,
) -> dict[str, object]:
    return {
        "tutor_name": "Konstantin",
        "lesson_id": lesson.lesson_id,
        "title": lesson.title,
        "student_id": lesson.student_id or "—",
        "student_name": lesson.student_name or "—",
        "start_hm": lesson.start_hm,
        "end_hm": lesson.end_hm,
        "duration_min": lesson.duration_min,
        "currency": lesson.currency,
        "planned_rate": lesson.planned_rate_snapshot or "—",
        "planned_charge": lesson.planned_charge_amount or "—",
        "actual_rate": lesson.actual_rate_snapshot or "—",
        "actual_charge": lesson.actual_charge_amount or "—",
        "lesson_status": _stringify_status(lesson.lesson_status),
        "confirmation_status": _stringify_status(lesson.confirmation_status),
        "meet_url": meet_url,
        "before_minutes": lesson.before_minutes,
    }


async def _build_google_calendar_client_if_needed(
    *,
    services: PipubotServices,
    tutor_user_id: int,
    candidates: list[LessonReminderCandidate],
):
    if not any(not lesson.meet_url for lesson in candidates):
        return None

    try:
        return await services.google_calendar.build_client(profile="KONSTANTIN")
    except GoogleOAuthReauthRequiredError:
        logger.warning(
            "[send_upcoming_lesson_reminder] google reauth required for tutor_user_id=%s",
            tutor_user_id,
        )
        return None
    except Exception:
        logger.exception(
            "[send_upcoming_lesson_reminder] failed to build GoogleCalendarClient "
            "for tutor_user_id=%s",
            tutor_user_id,
        )
        return None


async def _resolve_meet_url(
    *,
    session: AsyncSession,
    tutor_user_id: int,
    lesson: LessonReminderCandidate,
    client: object | None,
) -> str:
    if lesson.meet_url:
        return lesson.meet_url

    if client is None:
        return "—"

    try:
        ensured_meet_url = await ensure_lesson_meet_link(
            session=session,
            tutor_user_id=tutor_user_id,
            lesson_id=lesson.lesson_id,
            client=client,
        )
        return ensured_meet_url or "—"
    except Exception:
        logger.exception(
            "[send_upcoming_lesson_reminder] failed to ensure meet link "
            "for tutor_user_id=%s lesson_id=%s",
            tutor_user_id,
            lesson.lesson_id,
        )
        return "—"


async def _send_single_lesson_reminder(
    *,
    session: AsyncSession,
    services: PipubotServices,
    tutor_user_id: int,
    lesson: LessonReminderCandidate,
    client: object | None,
) -> None:
    meet_url = await _resolve_meet_url(
        session=session,
        tutor_user_id=tutor_user_id,
        lesson=lesson,
        client=client,
    )

    await services.interaction.notification_service.send(
        notification_key="test_notification",
        session=session,
        chat_id=tutor_user_id,
        text_vars=_build_notification_text_vars(lesson, meet_url),
        dedupe_key=lesson.dedupe_key,
    )


@background_task_handler(
    recurring_key="system.lesson_reminders.konstantin.10m",
    recurring_interval_seconds=1,
    recurring_payload_template={
        "tutor_user_id": int(os.environ["KONSTANTIN_USER_ID"]),
        "notify_before_minutes": 300,
    },
)
async def send_upcoming_lesson_reminder(
    session: AsyncSession,
    payload: LessonReminderPayload,
    services: PipubotServices,
) -> None:
    tutor_user_id = int(payload["tutor_user_id"])
    notify_before_minutes = int(payload.get("notify_before_minutes", 10))

    candidates = await build_upcoming_lesson_reminder_candidates(
        session,
        tutor_user_id=tutor_user_id,
        before_minutes=notify_before_minutes,
    )

    client = await _build_google_calendar_client_if_needed(
        services=services,
        tutor_user_id=tutor_user_id,
        candidates=candidates,
    )

    for lesson in candidates:
        await _send_single_lesson_reminder(
            session=session,
            services=services,
            tutor_user_id=tutor_user_id,
            lesson=lesson,
            client=client,
        )