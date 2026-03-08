from __future__ import annotations

from core.interaction.input.user_input import UserInput
from core.interaction.ui import Step
from core.interaction.ui.binding import step
from core.interaction.ui.components.process.effects import StepResult

from ..constants import CONFIRM_STEP, EDIT_INFO_STEP
from ..parser import parse_student_draft_patch_from_text
from ..payload import load_student_draft, merge_student_drafts, save_student_draft
from ..text_vars import student_draft_to_text_variables, format_error_block
from ..validators import validate_student_draft_for_create


@step(EDIT_INFO_STEP)
class EditStudentInfoStep(Step):
    async def _on_start(self, user_input: UserInput) -> None:
        draft = load_student_draft(user_input)
        self._patch_payload(
            user_input,
            text_variables=student_draft_to_text_variables(draft),
        )

    async def handle_message(self, user_input: UserInput) -> StepResult:
        message = (user_input.text or "").strip()

        parse_result = parse_student_draft_patch_from_text(message)
        patch = parse_result.draft

        if parse_result.errors:
            current_draft = load_student_draft(user_input)
            self._patch_payload(
                user_input,
                text_variables={
                    **student_draft_to_text_variables(current_draft),
                    "error": format_error_block(parse_result.errors),
                },
            )
            return None

        current_draft = load_student_draft(user_input)
        updated_draft = merge_student_drafts(
            base=current_draft,
            patch=patch,
        )

        validation_errors = validate_student_draft_for_create(
            tutor_user_id=user_input.telegram_id,
            draft=updated_draft,
        )
        if validation_errors:
            self._patch_payload(
                user_input,
                text_variables={
                    **student_draft_to_text_variables(updated_draft),
                    "error": format_error_block(validation_errors),
                },
            )
            return None

        save_student_draft(
            user_input,
            draft=updated_draft,
        )

        self._patch_payload(
            user_input,
            text_variables=student_draft_to_text_variables(updated_draft),
        )

        return self.go_to_step(CONFIRM_STEP)