from __future__ import annotations

from core.interaction.ui.binding import process
from core.interaction.ui.components.process.patterns.draft_create_process import DraftCreateProcess, \
    ConfirmStepCallbacks

from pipubot.domains.tutoring.students.results import StudentDraft
from pipubot.domains.tutoring.students.mapper import (
    draft_to_create_student_dto,
)
from pipubot.domains.tutoring.students.errors import CreateStudentError
from pipubot.domains.tutoring.students.create_service import (
    create_student_service,
)

from .schema import STUDENT_CREATE_SCHEMA


@process("add_student")
class AddStudentProcess(DraftCreateProcess[StudentDraft]):
    collect_step_name = "ask_student_add_info"
    edit_step_name = "edit_student_info"
    confirm_step_name = "confirm_add_student"

    @classmethod
    def schema(cls):
        return STUDENT_CREATE_SCHEMA

    @classmethod
    def draft_factory(cls):
        return StudentDraft

    def confirm_callbacks(self) -> ConfirmStepCallbacks:
        return ConfirmStepCallbacks(
            edit="edit",
            confirm="confirm",
        )

    def validate_draft(
            self,
            user_input,
            draft: StudentDraft,
    ) -> list[str]:
        errors: list[str] = []

        try:
            draft_to_create_student_dto(
                tutor_user_id=user_input.telegram_id,
                draft=draft,
            )
        except ValueError as e:
            errors.append(str(e))

        return errors

    async def submit_draft(
            self,
            user_input,
            draft: StudentDraft,
    ) -> None:
        dto = draft_to_create_student_dto(
            tutor_user_id=user_input.telegram_id,
            draft=draft,
        )

        student = await create_student_service(
            user_input.session,
            data=dto,
        )

        user_input.state.update_process_payload(
            self._key(),
            created_student_id=student.id,
        )

    def on_submit_error(
            self,
            user_input,
            *,
            draft: StudentDraft,
            error: Exception,
    ) -> list[str]:
        if isinstance(error, CreateStudentError):
            return [str(error)]
        return super().on_submit_error(
            user_input,
            draft=draft,
            error=error,
        )
