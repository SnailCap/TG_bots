from __future__ import annotations

from pipubot.domains.tutoring.dto.student_dto import (
    CreateStudentDTO,
    CreateStudentRepoPayload,
    StudentDraftDTO,
)
from pipubot.domains.tutoring.enums.enums import StudentState

from core.shared.normalize.currency import normalize_currency_code
from core.shared.normalize.strings import (
    normalize_optional_str,
    normalize_required_str,
)
from core.shared.normalize.telegram import normalize_telegram_username


def draft_to_create_student_dto(
    *,
    tutor_user_id: int,
    draft: StudentDraftDTO,
) -> CreateStudentDTO:
    """
    Convert a UI draft into a service DTO.

    Performs lightweight normalization:
    - trims strings
    - empty strings -> None for optional fields
    - strips leading '@' from telegram_username
    - uppercases default_currency
    """
    return CreateStudentDTO(
        tutor_user_id=tutor_user_id,
        full_name=normalize_required_str(draft.full_name, field_name="full_name"),
        user_telegram_id=draft.user_telegram_id,
        telegram_username=normalize_telegram_username(draft.telegram_username),
        telegram_link=normalize_optional_str(draft.telegram_link),
        email=normalize_optional_str(draft.email),
        google_drive_link=normalize_optional_str(draft.google_drive_link),
        school_grade=draft.school_grade,
        exam_track=draft.exam_track,
        study_language=draft.study_language,
        study_format=draft.study_format,
        started_on=draft.started_on,
        notes=normalize_optional_str(draft.notes),
        default_currency=normalize_currency_code(draft.default_currency),
        default_rate=draft.default_rate,
        default_duration_min=require_not_none(
            draft.default_duration_min,
            field_name="default_duration_min",
        ),
        planned_hours_per_week=draft.planned_hours_per_week,
        payment_account=draft.payment_account,
        student_state=draft.student_state or StudentState.ACTIVE,
    )


def create_student_dto_to_repo_payload(
    dto: CreateStudentDTO,
) -> CreateStudentRepoPayload:
    """
    Convert service DTO into repository payload.
    Final normalization boundary before persistence.
    """
    return CreateStudentRepoPayload(
        tutor_user_id=dto.tutor_user_id,
        full_name=normalize_required_str(dto.full_name, field_name="full_name"),
        user_telegram_id=dto.user_telegram_id,
        telegram_username=normalize_telegram_username(dto.telegram_username),
        telegram_link=normalize_optional_str(dto.telegram_link),
        email=normalize_optional_str(dto.email),
        google_drive_link=normalize_optional_str(dto.google_drive_link),
        school_grade=dto.school_grade,
        exam_track=dto.exam_track,
        study_language=dto.study_language,
        study_format=dto.study_format,
        started_on=dto.started_on,
        notes=normalize_optional_str(dto.notes),
        default_currency=normalize_currency_code(dto.default_currency),
        default_rate=dto.default_rate,
        default_duration_min=require_not_none(
            dto.default_duration_min,
            field_name="default_duration_min",
        ),
        planned_hours_per_week=dto.planned_hours_per_week,
        payment_account=dto.payment_account,
        student_state=dto.student_state,
    )


def require_not_none(value, *, field_name: str):
    if value is None:
        raise ValueError(f"{field_name} is required")
    return value