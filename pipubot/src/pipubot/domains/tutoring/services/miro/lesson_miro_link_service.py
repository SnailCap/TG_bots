from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.db.transactional import transactional
from core.shared.utils.time import utc_now
from pipubot.domains.tutoring.repositories.lesson_repository import (
    get_lesson_by_id,
    update_lesson_miro_url,
)


class LessonMiroLinkError(RuntimeError):
    pass


class LessonMiroNotFoundError(LessonMiroLinkError):
    pass


def _build_dummy_miro_url(*, lesson_id: int) -> str:
    """
    Temporary dummy Miro URL builder.

    Replace this with a real Miro board creation later.
    """
    return f"https://miro.example.local/boards/lesson-{lesson_id}"


@transactional
async def ensure_lesson_miro_link(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    lesson_id: int,
) -> str:
    lesson = await get_lesson_by_id(
        session,
        tutor_user_id=tutor_user_id,
        lesson_id=lesson_id,
        load_student=False,
    )
    if lesson is None:
        raise LessonMiroNotFoundError(
            f"Lesson {lesson_id} was not found for tutor_user_id={tutor_user_id}."
        )

    if getattr(lesson, "miro_url", None):
        return lesson.miro_url

    if lesson.start_at <= utc_now():
        raise LessonMiroLinkError(
            f"Miro board can be created only for future lessons. lesson_id={lesson_id}"
        )

    miro_url = _build_dummy_miro_url(lesson_id=lesson.id)

    updated = await update_lesson_miro_url(
        session,
        tutor_user_id=tutor_user_id,
        lesson_id=lesson_id,
        miro_url=miro_url,
    )
    if updated is None:
        raise LessonMiroNotFoundError(
            f"Lesson {lesson_id} disappeared during miro link update."
        )

    return miro_url