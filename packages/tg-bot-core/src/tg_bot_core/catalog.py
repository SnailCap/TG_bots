from __future__ import annotations

from typing import Any, Mapping

from jinja2 import Environment, StrictUndefined, TemplateError

from .project import ActionSpec, ProjectDefinition
from .project.models import ButtonSpec


class CatalogError(RuntimeError):
    pass


class CallbackCodec:
    """Telegram callback protocol contains only a short, stable project action id."""

    _PREFIX = "v3:a:"

    def encode(self, action_id: str) -> str:
        payload = f"{self._PREFIX}{action_id}"
        if len(payload.encode("utf-8")) > 64:
            raise CatalogError("Encoded callback exceeds Telegram's 64-byte limit.")
        return payload

    def decode(self, payload: str) -> str:
        if not payload.startswith(self._PREFIX):
            raise CatalogError("Callback is not a valid action.")
        action_id = payload.removeprefix(self._PREFIX)
        if not action_id:
            raise CatalogError("Callback action id is empty.")
        return action_id


class ProjectCatalog:
    def __init__(self, project: ProjectDefinition) -> None:
        self.project = project
        self._jinja = Environment(undefined=StrictUndefined, autoescape=False)
        self._actions = dict(project.actions)
        self._action_views = {
            button.id: view.id
            for view in project.views.values()
            for row in view.keyboard
            for button in row
        }

    def action(self, action_id: str, *, current_view: str | None = None) -> ActionSpec | None:
        if current_view is not None and self._action_views.get(action_id) != current_view:
            return None
        return self._actions.get(action_id)

    def render(self, view_id: str, variables: Mapping[str, Any]) -> tuple[str, tuple[tuple[ButtonSpec, ...], ...]]:
        try:
            view = self.project.views[view_id]
        except KeyError as error:
            raise CatalogError(f"Unknown view '{view_id}'.") from error
        source = view.text.inline
        if source is None and view.text.template:
            source = self.project.templates.get(view.text.template)
        if source is None:
            raise CatalogError(f"View '{view_id}' has no renderable text.")
        try:
            rendered = self._jinja.from_string(source).render(**variables)
        except TemplateError as error:
            raise CatalogError(f"Failed to render view '{view_id}': {error}") from error
        if not rendered.strip():
            raise CatalogError(f"View '{view_id}' rendered an empty Telegram message.")
        if len(rendered) > 4096:
            raise CatalogError(
                f"View '{view_id}' rendered {len(rendered)} characters; Telegram allows at most 4096."
            )
        return rendered, view.keyboard
