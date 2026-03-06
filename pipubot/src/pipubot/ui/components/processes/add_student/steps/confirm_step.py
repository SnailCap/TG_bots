from __future__ import annotations

from core.interaction.input.user_input import UserInput
from core.interaction.ui import Step
from core.interaction.ui.binding import step
from core.interaction.ui.components.process.effects import StepResult

from pipubot.domains.tutoring.mappers.student_mapper import draft_to_create_student_dto
from pipubot.domains.tutoring.services.student.student_service import (
    CreateStudentDuplicateLiveNameError,
    CreateStudentDuplicateUserLinkError,
    CreateStudentValidationError,
    create_student_service,
)

from ..constants import (
    ASK_INFO_STEP,
    CONFIRM_CREATE_CALLBACK,
    EDIT_CALLBACK,
    PROCESS_KEY,
)
from ..payload import load_student_draft
from ..text_vars import student_draft_to_text_variables


@step("confirm_add_student")
class ConfirmStudentStep(Step):
    async def _on_start(self, user_input: UserInput) -> None:
        draft = load_student_draft(user_input)
        self._patch_payload(
            user_input,
            text_variables=student_draft_to_text_variables(draft),
        )

    async def handle_callback(self, user_input: UserInput) -> StepResult:
        callback = user_input.step_callback

        if callback == EDIT_CALLBACK:
            return self.go_to_step(ASK_INFO_STEP)

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

        except CreateStudentDuplicateLiveNameError:
            self._patch_payload(
                user_input,
                text_variables={
                    "error": "Уже существует активный или приостановленный ученик с таким именем.",
                },
            )
            return self.go_to_step(ASK_INFO_STEP)

        except CreateStudentDuplicateUserLinkError:
            self._patch_payload(
                user_input,
                text_variables={
                    "error": "Этот Telegram-пользователь уже привязан к другому ученику.",
                },
            )
            return self.go_to_step(ASK_INFO_STEP)

        except CreateStudentValidationError as e:
            self._patch_payload(
                user_input,
                text_variables={
                    "error": str(e),
                },
            )
            return self.go_to_step(ASK_INFO_STEP)

        except ValueError as e:
            self._patch_payload(
                user_input,
                text_variables={
                    "error": str(e),
                },
            )
            return self.go_to_step(ASK_INFO_STEP)

        user_input.state.update_process_payload(
            PROCESS_KEY,
            created_student_id=student.id,
        )

        self._patch_payload(
            user_input,
            text_variables={
                "error": "",
            },
        )

        return self.finish()