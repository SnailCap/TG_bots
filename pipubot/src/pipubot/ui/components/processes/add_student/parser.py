from __future__ import annotations

from pipubot.domains.tutoring.dto.student_dto import StudentDraftDTO

from .schema import ALIAS_TO_FIELD_NAME, FIELD_SPEC_BY_NAME, POSITIONAL_FIELD_ORDER


def parse_student_draft_from_text(text: str) -> StudentDraftDTO:
    """
    Parsing rules:
    - leading lines without ":" are treated as positional values
      according to POSITIONAL_FIELD_ORDER
    - once a recognized keyword line is encountered, parser switches
      to keyword mode
    - lines without ":" after keyword mode are ignored
    - keyword values override positional values
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    positional_values: list[str] = []
    keyword_values: dict[str, str] = {}
    keyword_mode = False

    for line in lines:
        if ":" in line:
            raw_key, raw_value = line.split(":", 1)
            normalized_key = raw_key.strip().lower()
            normalized_value = raw_value.strip()

            field_name = ALIAS_TO_FIELD_NAME.get(normalized_key)
            if field_name is not None:
                keyword_mode = True
                keyword_values[field_name] = normalized_value
                continue

        if not keyword_mode:
            positional_values.append(line)

    draft = StudentDraftDTO()

    for index, raw_value in enumerate(positional_values):
        if index >= len(POSITIONAL_FIELD_ORDER):
            break

        field_name = POSITIONAL_FIELD_ORDER[index]
        field_schema = FIELD_SPEC_BY_NAME[field_name]
        setattr(draft, field_name, field_schema.parser(raw_value))

    for field_name, raw_value in keyword_values.items():
        field_schema = FIELD_SPEC_BY_NAME[field_name]
        setattr(draft, field_name, field_schema.parser(raw_value))

    return draft