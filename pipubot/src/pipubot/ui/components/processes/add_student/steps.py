from core.interaction.ui.components.process.patterns.draft_create_process import CollectDraftStep
from core.interaction.ui.components.process.patterns.draft_create_process import ConfirmDraftStep
from core.interaction.ui.binding import step
from core.interaction.ui.components.process.patterns.draft_create_process import (
    EditDraftStep,
)


@step("ask_student_add_info")
class AskStudentAddInfoStep(CollectDraftStep):
    pass


@step("confirm_add_student")
class ConfirmAddStudentStep(ConfirmDraftStep):
    pass


@step("edit_student_info")
class EditStudentInfoStep(EditDraftStep):
    pass
