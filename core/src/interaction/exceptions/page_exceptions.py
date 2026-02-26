class PrebuiltPageNotFoundError(Exception):
    """Raised when a requested prebuilt page is not found."""

    def __init__(self, page_name: str):
        self.page_name = page_name
        super().__init__(f"Prebuilt page '{page_name}' not found.")


class EmptyPageTextError(Exception):
    def __init__(self, page_name: str):
        self.page_name = page_name
        super().__init__(f"Page with name '{page_name}' has an empty text.")


class PageNotFoundError(Exception):
    def __init__(self, page_name):
        self.page_name = page_name
        super().__init__(f'Page with name "{page_name}" not found.')
