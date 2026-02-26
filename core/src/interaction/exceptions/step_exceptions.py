# src/interaction/exceptions/step_exceptions.py

class StepNotFoundError(Exception):
    def __init__(self, name: str):
        super().__init__(f"Step '{name}' not found in config.")
