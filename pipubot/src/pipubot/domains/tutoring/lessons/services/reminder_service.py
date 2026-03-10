from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from core.shared.utils.time import format_time_hm, upcoming_window_utc
from pipubot.domains.tutoring.lessons.contracts.queries import LessonReminderCandidate
from pipubot.domains.tutoring.lessons.repository import list_upcoming_lessons


def _duration_minutes_floor(start: datetime, end: datetime) -> int:
    seconds = (end - start).total_seconds()
    if seconds <= 0:
        return 0
    return int(seconds // 60)


async def build_upcoming_lesson_reminder_candidates(
        session: AsyncSession,
        *,
        tutor_user_id: int,
        before_minutes: int,
        limit: int = 200,
) -> list[LessonReminderCandidate]:
    window = upcoming_window_utc(before_minutes)

    lessons = await list_upcoming_lessons(
        session,
        tutor_user_id=tutor_user_id,
        start_from=window.start,
        start_to=window.end,
        limit=limit,
        load_student=True,
    )

    out: list[LessonReminderCandidate] = []

    for lesson in lessons:
        title = (lesson.title or "").strip() or "Урок"

        start_hm = format_time_hm(lesson.start_at)
        end_hm = format_time_hm(lesson.end_at)
        duration_min = _duration_minutes_floor(lesson.start_at, lesson.end_at)

        student_id: int | None = lesson.student_id
        student_name: str | None = None
        if lesson.student is not None:
            student_name = (lesson.student.full_name or "").strip() or None

        dedupe_key = (
            f"lesson_reminder:{tutor_user_id}:"
            f"{lesson.id}:{before_minutes}:{lesson.start_at.isoformat()}"
        )

        out.append(
            LessonReminderCandidate(
                chat_id=tutor_user_id,
                dedupe_key=dedupe_key,
                tutor_user_id=tutor_user_id,
                before_minutes=before_minutes,
                lesson_id=lesson.id,
                student_id=student_id,
                student_name=student_name,
                start_at=lesson.start_at,
                end_at=lesson.end_at,
                start_hm=start_hm,
                end_hm=end_hm,
                duration_min=duration_min,
                title=title,
                meet_url=lesson.meet_url,
                currency=lesson.currency,
                planned_rate_snapshot=lesson.planned_rate_snapshot,
                planned_charge_amount=lesson.planned_charge_amount,
                actual_rate_snapshot=lesson.actual_rate_snapshot,
                actual_charge_amount=lesson.actual_charge_amount,
                lesson_status=lesson.status,
                confirmation_status=lesson.confirmation_status,
            )
        )

    return out
