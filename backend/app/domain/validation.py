from dataclasses import dataclass

from .enums import ValidationSeverity


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    severity: ValidationSeverity
    code: str
    message: str
    entity_type: str | None = None
    entity_id: str | None = None
    path: str | None = None
    hint: str | None = None

