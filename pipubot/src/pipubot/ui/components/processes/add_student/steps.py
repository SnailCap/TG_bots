from __future__ import annotations

from core.interaction.ui.binding import step
from core.interaction.ui.components.process.patterns.object_input import (
    ConfirmObjectStep,
    EditObjectStep,
    InputObjectStep,
)


@step("ask_student_add_info")
class AskStudentAddInfoStep(InputObjectStep):
    pass


@step("confirm_add_student")
class ConfirmAddStudentStep(ConfirmObjectStep):
    pass


@step("edit_student_info")
class EditStudentInfoStep(EditObjectStep):
    pass