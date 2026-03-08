from __future__ import annotations

from core.interaction.input.user_input import UserInput
from core.interaction.ui import Step
from core.interaction.ui.binding import step
from core.interaction.ui.components.process.effects import StepResult

from ..constants import CONFIRM_STEP
from ..parser import parse_student_draft_from_text
from ..payload import save_student_draft
from ..text_vars import student_draft_to_text_variables
from ..validators import validate_student_draft_for_create


@step("ask_student_add_info")
class AskInfoStep(Step):
    async def handle_message(self, user_input: UserInput) -> StepResult:
        message = (user_input.text or "").strip()

        parse_result = parse_student_draft_from_text(message)
        draft = parse_result.draft

        errors = [
            *parse_result.errors,
            *validate_student_draft_for_create(
                tutor_user_id=user_input.telegram_id,
                draft=draft,
            ),
        ]

        if errors:
            self._patch_payload(
                user_input,
                text_variables={
                    **student_draft_to_text_variables(draft),
                    "error": "\n".join(errors),
                },
            )
            return None

        save_student_draft(
            user_input,
            draft=draft,
        )

        self._patch_payload(
            user_input,
            text_variables=student_draft_to_text_variables(draft),
        )

        return self.go_to_step(CONFIRM_STEP)