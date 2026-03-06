from __future__ import annotations

from dataclasses import asdict

from core.interaction.input.user_input import UserInput
from pipubot.domains.tutoring.dto.student_dto import StudentDraftDTO

from .constants import PROCESS_KEY
from .schema import STUDENT_FIELD_SPECS


def student_draft_to_payload_dict(draft: StudentDraftDTO) -> dict:
    data = asdict(draft)

    for spec in STUDENT_FIELD_SPECS:
        raw_value = data.get(spec.field_name)
        data[spec.field_name] = spec.serializer(raw_value)

    return data


def payload_dict_to_student_draft(data: dict) -> StudentDraftDTO:
    draft_data = dict(data)

    for spec in STUDENT_FIELD_SPECS:
        if spec.field_name not in draft_data:
            continue

        draft_data[spec.field_name] = spec.deserializer(
            draft_data[spec.field_name]
        )

    return StudentDraftDTO(**draft_data)


def load_student_draft(user_input: UserInput) -> StudentDraftDTO:
    payload = user_input.state.get_process_payload(PROCESS_KEY)
    draft_data = payload.get("student_draft") or {}
    return payload_dict_to_student_draft(draft_data)


def save_student_draft(
    user_input: UserInput,
    *,
    draft: StudentDraftDTO,
) -> None:
    user_input.state.update_process_payload(
        PROCESS_KEY,
        student_draft=student_draft_to_payload_dict(draft),
    )