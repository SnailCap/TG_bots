from __future__ import annotations

from html import escape as html_escape
from typing import Any, Mapping, Final

from jinja2 import Environment, StrictUndefined, TemplateError

from core.interaction.exceptions.template_errors import PlaceholderFormatError
from core.interaction.ui.templating.text_renderer import TextRenderer


class JinjaTextRenderer(TextRenderer):
    def __init__(self) -> None:
        self._env: Final[Environment] = Environment(
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
            undefined=StrictUndefined,
        )

    def render(
        self,
        template: str,
        variables: Mapping[str, Any],
        *,
        html_escape_variables: bool = False,
    ) -> str:
        try:
            render_vars = self._prepare_variables(
                variables,
                html_escape_variables=html_escape_variables,
            )
            return self._env.from_string(template).render(**render_vars)
        except TemplateError as e:
            raise PlaceholderFormatError(template, dict(variables), e) from e
        except Exception as e:
            raise PlaceholderFormatError(template, dict(variables), e) from e

    @staticmethod
    def _prepare_variables(
        variables: Mapping[str, Any],
        *,
        html_escape_variables: bool,
    ) -> dict[str, Any]:
        if not html_escape_variables:
            return dict(variables)

        return {
            key: html_escape(value) if isinstance(value, str) else value
            for key, value in variables.items()
        }