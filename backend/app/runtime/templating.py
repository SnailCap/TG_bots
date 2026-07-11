from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from jinja2 import StrictUndefined, TemplateError
from jinja2.sandbox import SandboxedEnvironment

from .errors import BotRuntimeError


class TemplateRenderError(BotRuntimeError):
    code = "template_render_error"


class StrictTemplateRenderer:
    """Strict, sandboxed Jinja renderer for project-authored message templates."""

    def __init__(self) -> None:
        self._environment = SandboxedEnvironment(
            autoescape=False,
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
            enable_async=False,
        )

    def render(self, template: str, variables: Mapping[str, Any]) -> str:
        try:
            return self._environment.from_string(template).render(
                **self.build_context(variables)
            )
        except TemplateError as exc:
            raise TemplateRenderError(f"Cannot render template: {exc}") from exc

    def render_value(self, value: Any, variables: Mapping[str, Any]) -> Any:
        if isinstance(value, str):
            return self.render(value, variables)
        if isinstance(value, list):
            return [self.render_value(item, variables) for item in value]
        if isinstance(value, tuple):
            return tuple(self.render_value(item, variables) for item in value)
        if isinstance(value, dict):
            return {
                str(key): self.render_value(item, variables)
                for key, item in value.items()
            }
        return value

    @staticmethod
    def build_context(variables: Mapping[str, Any]) -> dict[str, Any]:
        """Expose both literal keys and dotted keys as nested mappings."""
        context: dict[str, Any] = dict(variables)
        for raw_key, value in variables.items():
            parts = [part for part in str(raw_key).split(".") if part]
            if len(parts) < 2:
                continue
            cursor = context
            for part in parts[:-1]:
                nested = cursor.get(part)
                if not isinstance(nested, dict):
                    nested = {}
                    cursor[part] = nested
                cursor = nested
            cursor[parts[-1]] = value
        return context

