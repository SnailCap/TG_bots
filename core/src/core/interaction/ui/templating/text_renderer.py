from __future__ import annotations

from typing import Protocol, Mapping, Any


class TextRenderer(Protocol):
    def render(
        self,
        template: str,
        variables: Mapping[str, Any],
        *,
        html_escape_variables: bool = False,
    ) -> str: ...