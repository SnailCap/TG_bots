from __future__ import annotations

from .fields import STUDENT_FIELD_SPECS


FIELD_SPEC_BY_NAME: dict[str, object] = {
    spec.field_name: spec
    for spec in STUDENT_FIELD_SPECS
}

ALIAS_TO_FIELD_NAME: dict[str, str] = {
    alias.strip().lower(): spec.field_name
    for spec in STUDENT_FIELD_SPECS
    for alias in spec.aliases
}

POSITIONAL_FIELD_ORDER: tuple[str, ...] = tuple(
    spec.field_name
    for spec in STUDENT_FIELD_SPECS
    if spec.allow_positional
)