class ProcessNotFoundError(Exception):
    def __init__(self, process_name: str):
        super().__init__(f"Process with the name '{process_name}' not found.")
        self.process_name = process_name
