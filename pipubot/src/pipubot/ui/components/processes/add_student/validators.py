from __future__ import annotations

from pipubot.domains.tutoring.dto.student_dto import StudentDraftDTO
from pipubot.domains.tutoring.mappers.student_mapper import draft_to_create_student_dto

from .schema import STUDENT_FIELD_SPECS


def validate_student_draft_for_create(
    *,
    tutor_user_id: int,
    draft: StudentDraftDTO,
) -> list[str]:
    errors: list[str] = []

    try:
        draft_to_create_student_dto(
            tutor_user_id=tutor_user_id,
            draft=draft,
        )
    except ValueError as e:
        errors.append(str(e))

    for spec in STUDENT_FIELD_SPECS:
        if spec.validator is None:
            continue

        value = getattr(draft, spec.field_name)
        error = spec.validator(value)
        if error:
            errors.append(error)

    return errors