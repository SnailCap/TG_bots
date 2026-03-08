from __future__ import annotations

from dataclasses import dataclass

from pipubot.domains.tutoring.dto.student_dto import StudentDraftDTO

from .schema import ALIAS_TO_FIELD_NAME, FIELD_SPEC_BY_NAME, POSITIONAL_FIELD_ORDER


@dataclass(frozen=True, slots=True)
class StudentDraftParseResult:
    draft: StudentDraftDTO
    errors: list[str]


def _normalize_non_empty_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _try_parse_keyword_line(line: str) -> tuple[str, str] | None:
    if ":" not in line:
        return None

    raw_key, raw_value = line.split(":", 1)
    normalized_key = raw_key.strip().lower()
    normalized_value = raw_value.strip()

    field_name = ALIAS_TO_FIELD_NAME.get(normalized_key)
    if field_name is None:
        return None

    return field_name, normalized_value


def _set_parsed_field_value(
    draft: StudentDraftDTO,
    *,
    field_name: str,
    raw_value: str,
    errors: list[str],
) -> None:
    field_spec = FIELD_SPEC_BY_NAME[field_name]

    try:
        parsed_value = field_spec.parser(raw_value)
    except ValueError as e:
        errors.append(f"{field_spec.label}: {e}")
        return

    setattr(draft, field_name, parsed_value)


def parse_student_draft_from_text(text: str) -> StudentDraftParseResult:
    """
    Mixed parser for an initial info step.

    Rules:
    - leading lines without ":" are treated as positional values
      according to POSITIONAL_FIELD_ORDER
    - once a recognized keyword line is encountered, parser switches
      to keyword mode
    - in keyword mode, each line must be "key: value"
    - keyword values override positional values
    """
    lines = _normalize_non_empty_lines(text)

    positional_values: list[str] = []
    keyword_values: dict[str, str] = {}
    errors: list[str] = []

    keyword_mode = False

    for line in lines:
        parsed_keyword = _try_parse_keyword_line(line)
        if parsed_keyword is not None:
            field_name, normalized_value = parsed_keyword
            keyword_mode = True
            keyword_values[field_name] = normalized_value
            continue

        if keyword_mode:
            errors.append(
                f"Строка '{line}' должна быть в формате 'ключ: значение' "
                "с корректным названием поля."
            )
            continue

        positional_values.append(line)

    draft = StudentDraftDTO()

    for index, raw_value in enumerate(positional_values):
        if index >= len(POSITIONAL_FIELD_ORDER):
            errors.append(
                f"Слишком много позиционных строк. Лишнее значение: '{raw_value}'."
            )
            continue

        field_name = POSITIONAL_FIELD_ORDER[index]
        _set_parsed_field_value(
            draft,
            field_name=field_name,
            raw_value=raw_value,
            errors=errors,
        )

    for field_name, raw_value in keyword_values.items():
        _set_parsed_field_value(
            draft,
            field_name=field_name,
            raw_value=raw_value,
            errors=errors,
        )

    return StudentDraftParseResult(
        draft=draft,
        errors=errors,
    )


def parse_student_draft_patch_from_text(text: str) -> StudentDraftParseResult:
    """
    Strict keyword-only parser for an edit step.

    Rules:
    - Every non-empty line must be in "key: value" format
    - only recognized keys are allowed
    - unknown keys are reported as errors
    - Invalid values are reported as field-level errors
    """
    lines = _normalize_non_empty_lines(text)

    draft = StudentDraftDTO()
    errors: list[str] = []

    for line in lines:
        if ":" not in line:
            errors.append(
                f"Строка '{line}' должна быть в формате 'ключ: значение'."
            )
            continue

        raw_key, raw_value = line.split(":", 1)
        normalized_key = raw_key.strip().lower()
        normalized_value = raw_value.strip()

        field_name = ALIAS_TO_FIELD_NAME.get(normalized_key)
        if field_name is None:
            errors.append(f"Неизвестное поле: '{raw_key.strip()}'.")
            continue

        _set_parsed_field_value(
            draft,
            field_name=field_name,
            raw_value=normalized_value,
            errors=errors,
        )

    return StudentDraftParseResult(
        draft=draft,
        errors=errors,
    )