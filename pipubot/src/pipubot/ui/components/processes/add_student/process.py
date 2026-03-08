from __future__ import annotations

from core.interaction.ui import Process
from core.interaction.ui.binding import process

from .constants import ASK_INFO_STEP, CONFIRM_STEP, EDIT_INFO_STEP, PROCESS_KEY


@process(PROCESS_KEY)
class AddStudentProcess(Process):
    step_names = [
        ASK_INFO_STEP,
        EDIT_INFO_STEP,
        CONFIRM_STEP,
    ]