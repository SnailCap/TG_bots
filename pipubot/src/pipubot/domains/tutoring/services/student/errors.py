from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class CreateStudentError(ValueError):
    message: str

    def __str__(self) -> str:
        return self.message
