from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from core.db.transactional import transactional
from core.shared.utils.time import utc_now
from pipubot.domains.tutoring.enums.lesson import LessonStatus
from pipubot.domains.tutoring.integrations.google_calendar.protocols import CalendarClient
from pipubot.domains.tutoring.lessons.contracts.results import LessonPreparationStats
from pipubot.domains.tutoring.lessons.repository import list_upcoming_lessons
from pipubot.domains.tutoring.lessons.services.meet_link_service import (
    ensure_lesson_meet_link,
)
from pipubot.domains.tutoring.lessons.errors import LessonMeetLinkError, LessonNotFoundError, \
    LessonGoogleEventBindingError, LessonMiroLinkError, LessonMiroNotFoundError
from pipubot.domains.tutoring.lessons.services.miro_link_service import ensure_lesson_miro_link


@transactional
async def prepare_upcoming_lessons_for_delivery(
        session: AsyncSession,
        *,
        tutor_user_id: int,
        client: CalendarClient,
        lookahead_minutes: int = 24 * 60,
        miro_lookahead_minutes: int = 15,
        limit: int = 200,
        now: datetime | None = None,
) -> LessonPreparationStats:
    now = now or utc_now()

    meet_window_end = now + timedelta(minutes=lookahead_minutes)
    miro_window_end = now + timedelta(minutes=miro_lookahead_minutes)

    lessons = await list_upcoming_lessons(
        session,
        tutor_user_id=tutor_user_id,
        start_from=now,
        start_to=meet_window_end,
        limit=limit,
        load_student=False,
    )

    scanned_lessons = 0

    prepared_meet_links = 0
    prepared_miro_boards = 0

    skipped_existing_meet_links = 0
    skipped_existing_miro_boards = 0

    skipped_non_planned = 0
    skipped_past_or_started = 0
    skipped_unbound = 0

    failed_meet = 0
    failed_miro = 0

    for lesson in lessons:
        scanned_lessons += 1

        if lesson.status != LessonStatus.PLANNED:
            skipped_non_planned += 1
            continue

        if lesson.start_at <= now:
            skipped_past_or_started += 1
            continue

        # ----------------------------------------------------------
        # Meet: broad preparation window
        # ----------------------------------------------------------

        if lesson.meet_url:
            skipped_existing_meet_links += 1
        else:
            try:
                await ensure_lesson_meet_link(
                    session,
                    tutor_user_id=tutor_user_id,
                    lesson_id=lesson.id,
                    client=client,
                )
                prepared_meet_links += 1

            except (LessonGoogleEventBindingError, LessonNotFoundError):
                skipped_unbound += 1

            except LessonMeetLinkError:
                skipped_past_or_started += 1

            except Exception:
                failed_meet += 1

        # ----------------------------------------------------------
        # Miro: short pre-lesson window (e.g. 15 minutes)
        # ----------------------------------------------------------

        if lesson.start_at > miro_window_end:
            continue

        if getattr(lesson, "miro_url", None):
            skipped_existing_miro_boards += 1
            continue

        try:
            await ensure_lesson_miro_link(
                session,
                tutor_user_id=tutor_user_id,
                lesson_id=lesson.id,
            )
            prepared_miro_boards += 1

        except LessonMiroNotFoundError:
            skipped_unbound += 1

        except LessonMiroLinkError:
            skipped_past_or_started += 1

        except Exception:
            failed_miro += 1

    return LessonPreparationStats(
        scanned_lessons=scanned_lessons,
        prepared_meet_links=prepared_meet_links,
        prepared_miro_boards=prepared_miro_boards,
        skipped_existing_meet_links=skipped_existing_meet_links,
        skipped_existing_miro_boards=skipped_existing_miro_boards,
        skipped_non_planned=skipped_non_planned,
        skipped_past_or_started=skipped_past_or_started,
        skipped_unbound=skipped_unbound,
        failed_meet=failed_meet,
        failed_miro=failed_miro,
    )
