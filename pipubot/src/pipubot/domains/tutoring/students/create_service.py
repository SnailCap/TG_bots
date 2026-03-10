from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from pipubot.domains.tutoring.students.commands import CreateStudent, CreateStudentPersistPayload
from pipubot.domains.tutoring.students.mapper import (
    create_student_dto_to_repo_payload,
)
from pipubot.domains.tutoring.models.student import TutoringStudent
from pipubot.domains.tutoring.students.repository import (
    create_student,
    get_live_student_by_full_name_ci,
    get_student_by_user_telegram_id,
)
from pipubot.domains.tutoring.students.errors import CreateStudentError


async def create_student_service(
    session: AsyncSession,
    *,
    data: CreateStudent,
) -> TutoringStudent:
    payload = _build_payload_or_raise(data)

    _validate_business_rules(payload)

    existing_by_name = await get_live_student_by_full_name_ci(
        session,
        tutor_user_id=payload.tutor_user_id,
        full_name=payload.full_name,
    )
    if existing_by_name is not None:
        raise CreateStudentError(
            "Уже существует активный или приостановленный ученик с таким именем."
        )

    if payload.user_telegram_id is not None:
        existing_by_user = await get_student_by_user_telegram_id(
            session,
            tutor_user_id=payload.tutor_user_id,
            user_telegram_id=payload.user_telegram_id,
        )
        if existing_by_user is not None:
            raise CreateStudentError(
                "Этот Telegram-пользователь уже привязан к другому ученику."
            )

    return await create_student(session, payload=payload)


def _build_payload_or_raise(data: CreateStudent) -> CreateStudentPersistPayload:
    try:
        return create_student_dto_to_repo_payload(data)
    except ValueError as e:
        raise CreateStudentError(str(e)) from e


def _validate_business_rules(payload: CreateStudentPersistPayload) -> None:
    if payload.default_duration_min <= 0:
        raise CreateStudentError(
            "Длительность урока должна быть больше 0."
        )

    if payload.default_rate is not None and payload.default_rate <= 0:
        raise CreateStudentError(
            "Ставка должна быть больше 0."
        )

    if (
        payload.planned_hours_per_week is not None
        and payload.planned_hours_per_week <= 0
    ):
        raise CreateStudentError(
            "План часов в неделю должен быть больше 0."
        )