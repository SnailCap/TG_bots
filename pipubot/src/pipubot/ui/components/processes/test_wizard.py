from core.interaction.ui.binding.decorators import process
from core.interaction.ui.components.process.base_process import Process


@process("test_wizard")
class TestWizardProcess(Process):
    step_names = [
        "test_step_1",
        "test_step_2",
        "test_step_3",
    ]
