from __future__ import annotations

from core.interaction.input.user_input import UserInput
from core.interaction.ui import Step
from core.interaction.ui.binding import step
from core.interaction.ui.components.process.effects import StepResult

from pipubot.domains.tutoring.mappers.student_mapper import draft_to_create_student_dto
from pipubot.domains.tutoring.services.student.errors import CreateStudentError
from pipubot.domains.tutoring.services.student.student_service import (
    create_student_service,
)

from ..constants import (
    CONFIRM_CREATE_CALLBACK,
    EDIT_CALLBACK,
    EDIT_INFO_STEP,
    PROCESS_KEY,
)
from ..payload import load_student_draft
from ..text_vars import student_draft_to_text_variables, format_error_block


@step("confirm_add_student")
class ConfirmStudentStep(Step):
    async def _on_start(self, user_input: UserInput) -> None:
        draft = load_student_draft(user_input)
        self._patch_payload(
            user_input,
            text_variables=student_draft_to_text_variables(draft),
        )

    def _go_to_edit_with_error(
        self,
        user_input: UserInput,
        *,
        error_message: str,
    ) -> StepResult:
        self._patch_payload(
            user_input,
            text_variables={"error": format_error_block([error_message])},
        )
        return self.go_to_step(EDIT_INFO_STEP)

    async def handle_callback(self, user_input: UserInput) -> StepResult:
        callback = user_input.step_callback

        if callback == EDIT_CALLBACK:
            return self.go_to_step(EDIT_INFO_STEP)

        if callback != CONFIRM_CREATE_CALLBACK:
            return None

        draft = load_student_draft(user_input)

        try:
            dto = draft_to_create_student_dto(
                tutor_user_id=user_input.telegram_id,
                draft=draft,
            )
            student = await create_student_service(
                user_input.session,
                data=dto,
            )
        except CreateStudentError as e:
            return self._go_to_edit_with_error(
                user_input,
                error_message=str(e),
            )

        user_input.state.update_process_payload(
            PROCESS_KEY,
            created_student_id=student.id,
        )

        self._patch_payload(
            user_input,
            text_variables={"error": ""},
        )

        return self.finish()