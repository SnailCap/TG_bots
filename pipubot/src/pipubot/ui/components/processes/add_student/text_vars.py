from __future__ import annotations

from pipubot.domains.tutoring.dto.student_dto import StudentDraftDTO

from .schema import STUDENT_FIELD_SPECS


def student_draft_to_text_variables(draft: StudentDraftDTO) -> dict[str, str]:
    variables: dict[str, str] = {"error": ""}

    for spec in STUDENT_FIELD_SPECS:
        if not spec.include_in_confirm:
            continue

        value = getattr(draft, spec.field_name)
        variables[spec.field_name] = spec.formatter(value)

    return variables

def format_error_block(errors: list[str]) -> str:
    if not errors:
        return ""

    formatted_lines = "\n".join(f"• {error}" for error in errors)
    return f"⚠ Ошибка:\n{formatted_lines}\n"