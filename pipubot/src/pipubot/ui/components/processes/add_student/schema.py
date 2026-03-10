from __future__ import annotations

from core.interaction.ui.components.process.patterns.draft_create_process import DraftSchema
from pipubot.domains.tutoring.students.results import StudentDraft

from .fields import STUDENT_FIELD_SPECS

STUDENT_CREATE_SCHEMA = DraftSchema[StudentDraft](
    fields=STUDENT_FIELD_SPECS,
)