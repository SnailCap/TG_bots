from __future__ import annotations


class PlaceholderFormatError(ValueError):
    def __init__(self, template: str, variables: dict, original: Exception):
        super().__init__(
            f"Failed to format template: {template!r} with variables={variables}. Error: {original}"
        )
        self.template = template
        self.variables = variables
        self.original = original
