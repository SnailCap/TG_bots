from __future__ import annotations

from core.interaction.ui.components.process.patterns.draft_create_process import DraftSchema
from pipubot.domains.tutoring.dto.student_dto import StudentDraftDTO

from .fields import STUDENT_FIELD_SPECS

STUDENT_CREATE_SCHEMA = DraftSchema[StudentDraftDTO](
    fields=STUDENT_FIELD_SPECS,
)