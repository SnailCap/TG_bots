from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from pipubot.domains.tutoring.dto.student_dto import (
    CreateStudentDTO,
    CreateStudentRepoPayload,
)
from pipubot.domains.tutoring.mappers.student_mapper import create_student_dto_to_repo_payload
from pipubot.domains.tutoring.models.student import TutoringStudent
from pipubot.domains.tutoring.repositories.student_repository import (
    create_student,
    get_live_student_by_full_name_ci,
    get_student_by_user_telegram_id,
)


class CreateStudentError(ValueError):
    pass


class CreateStudentValidationError(CreateStudentError):
    pass


class CreateStudentDuplicateLiveNameError(CreateStudentError):
    pass


class CreateStudentDuplicateUserLinkError(CreateStudentError):
    pass


async def create_student_service(
    session: AsyncSession,
    *,
    data: CreateStudentDTO,
) -> TutoringStudent:
    payload = _build_payload_or_raise(data)

    _validate_business_rules(payload)

    existing_by_name = await get_live_student_by_full_name_ci(
        session,
        tutor_user_id=payload.tutor_user_id,
        full_name=payload.full_name,
    )
    if existing_by_name is not None:
        raise CreateStudentDuplicateLiveNameError(
            "Live student with this name already exists."
        )

    if payload.user_telegram_id is not None:
        existing_by_user = await get_student_by_user_telegram_id(
            session,
            tutor_user_id=payload.tutor_user_id,
            user_telegram_id=payload.user_telegram_id,
        )
        if existing_by_user is not None:
            raise CreateStudentDuplicateUserLinkError(
                "This Telegram user is already linked to a student."
            )

    return await create_student(session, payload=payload)


def _build_payload_or_raise(data: CreateStudentDTO) -> CreateStudentRepoPayload:
    try:
        return create_student_dto_to_repo_payload(data)
    except ValueError as e:
        raise CreateStudentValidationError(str(e)) from e


def _validate_business_rules(payload: CreateStudentRepoPayload) -> None:
    if payload.default_duration_min <= 0:
        raise CreateStudentValidationError(
            "default_duration_min must be > 0."
        )

    if payload.default_rate is not None and payload.default_rate <= 0:
        raise CreateStudentValidationError(
            "default_rate must be > 0."
        )

    if payload.planned_hours_per_week is not None and payload.planned_hours_per_week <= 0:
        raise CreateStudentValidationError(
            "planned_hours_per_week must be > 0."
        )