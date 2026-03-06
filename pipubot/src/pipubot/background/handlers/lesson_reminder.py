from __future__ import annotations

import os

from sqlalchemy.ext.asyncio import AsyncSession

from core.background.handler_registry import background_task_handler, TaskPayload
from pipubot.domains.tutoring.services.lesson.lesson_reminder_service import (
    build_upcoming_lesson_reminder_candidates,
)
from pipubot.runtime.runtime_services import DefaultAppServices


class LessonReminderPayload(TaskPayload):
    tutor_user_id: int
    notify_before_minutes: int


@background_task_handler(
    recurring_key="system.lesson_reminders.konstantin.10m",
    recurring_interval_seconds=30,
    recurring_payload_template={
        "tutor_user_id": int(os.environ["KONSTANTIN_USER_ID"]),
        "notify_before_minutes": 10,
    },
)
async def send_upcoming_lesson_reminder(
    session: AsyncSession,
    payload: LessonReminderPayload,
    services: DefaultAppServices,
) -> None:
    tutor_user_id = int(payload["tutor_user_id"])
    notify_before_minutes = int(payload.get("notify_before_minutes", 10))

    candidates = await build_upcoming_lesson_reminder_candidates(
        session,
        tutor_user_id=tutor_user_id,
        before_minutes=notify_before_minutes,
    )

    for lesson in candidates:
        await services.interaction.notification_service.send(
            notification_key="test_notification",
            session=session,
            chat_id=tutor_user_id,
            text_vars={
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
                "lesson_status": lesson.lesson_status.value if hasattr(lesson.lesson_status, "value") else str(lesson.lesson_status),
                "confirmation_status": lesson.confirmation_status.value if hasattr(lesson.confirmation_status, "value") else str(
                    lesson.confirmation_status),
                "meet_url": lesson.meet_url or "—",
                "before_minutes": lesson.before_minutes,
            },
            dedupe_key=lesson.dedupe_key,
        )