from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.db.transactional import transactional
from core.shared.utils.time import utc_now
from pipubot.domains.tutoring.integrations.google_calendar.protocols import (
    CalendarClient,
)
from pipubot.domains.tutoring.repositories.lesson_repository import (
    get_lesson_by_id,
    update_lesson_meet_url,
)


class LessonMeetLinkError(RuntimeError):
    pass


class LessonNotFoundError(LessonMeetLinkError):
    pass


class LessonGoogleEventBindingError(LessonMeetLinkError):
    pass


@transactional
async def ensure_lesson_meet_link(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    lesson_id: int,
    client: CalendarClient,
) -> str:
    lesson = await get_lesson_by_id(
        session,
        tutor_user_id=tutor_user_id,
        lesson_id=lesson_id,
        load_student=False,
    )
    if lesson is None:
        raise LessonNotFoundError(
            f"Lesson {lesson_id} was not found for tutor_user_id={tutor_user_id}."
        )

    if lesson.meet_url:
        return lesson.meet_url

    if lesson.start_at <= utc_now():
        raise LessonMeetLinkError(
            f"Meet link can be created only for future lessons. lesson_id={lesson_id}"
        )

    if not lesson.google_calendar_id or not lesson.google_event_id:
        raise LessonGoogleEventBindingError(
            f"Lesson {lesson_id} is not linked to a Google Calendar event."
        )

    meet_url = await client.ensure_event_meet_link(
        calendar_id=lesson.google_calendar_id,
        event_id=lesson.google_event_id,
    )

    updated = await update_lesson_meet_url(
        session,
        tutor_user_id=tutor_user_id,
        lesson_id=lesson_id,
        meet_url=meet_url,
    )
    if updated is None:
        raise LessonNotFoundError(
            f"Lesson {lesson_id} disappeared during meet link update."
        )

    return meet_url