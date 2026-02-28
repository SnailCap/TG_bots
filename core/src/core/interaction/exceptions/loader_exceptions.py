class TextFileNotFoundError(Exception):
    def __init__(self, file_name):
        self.file_name = file_name
        super().__init__(f'File "{file_name}" not found.')


