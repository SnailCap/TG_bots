from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

from jinja2 import Environment, StrictUndefined, TemplateError


ActionType = Literal["navigate", "flow.start", "flow.cancel", "flow.event"]


@dataclass(frozen=True, slots=True)
class ViewAction:
    type: ActionType
    target: str | None = None


@dataclass(frozen=True, slots=True)
class ViewButton:
    text: str
    action: ViewAction


@dataclass(frozen=True, slots=True)
class ViewDefinition:
    id: str
    inline_text: str | None
    template: str | None
    keyboard: tuple[tuple[ViewButton, ...], ...]


@dataclass(frozen=True, slots=True)
class BotManifest:
    entry_view: str
    start_flow: str
    schema_version: int = 2


class ResourceError(RuntimeError):
    pass


class CallbackCodec:
    """Compact transport protocol owned by core rather than resource authors."""

    _PREFIX = "v2:"
    _CODES = {"navigate": "n", "flow.start": "s", "flow.cancel": "c", "flow.event": "e"}
    _TYPES = {value: key for key, value in _CODES.items()}

    def encode(self, action: ViewAction) -> str:
        code = self._CODES[action.type]
        value = action.target or ""
        payload = f"{self._PREFIX}{code}:{value}"
        if len(payload.encode("utf-8")) > 64:
            raise ResourceError("Encoded callback exceeds Telegram's 64-byte limit.")
        return payload

    def decode(self, payload: str) -> ViewAction:
        if not payload.startswith(self._PREFIX):
            raise ResourceError("Callback is not a core v2 action.")
        _, code, target = payload.split(":", 2)
        try:
            action_type = self._TYPES[code]
        except KeyError as error:
            raise ResourceError(f"Unknown callback action code '{code}'.") from error
        if action_type in {"navigate", "flow.start", "flow.event"} and not target:
            raise ResourceError(f"Action '{action_type}' requires a target.")
        return ViewAction(action_type, target or None)


class ViewCatalog:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._manifest: BotManifest | None = None
        self._views: dict[str, ViewDefinition] = {}
        self._templates: dict[str, str] = {}
        self._jinja = Environment(undefined=StrictUndefined, autoescape=False)

    @property
    def manifest(self) -> BotManifest:
        if self._manifest is None:
            raise ResourceError("Catalog has not been loaded.")
        return self._manifest

    async def load(self) -> None:
        manifest_path = self._root / "bot.json"
        manifest = self._read_object(manifest_path)
        if manifest.get("schema_version") != 2:
            raise ResourceError("resources/bot.json must declare schema_version 2.")
        entry_view = self._required_string(manifest, "entry_view", manifest_path)
        start_flow = self._required_string(manifest, "start_flow", manifest_path)
        views: dict[str, ViewDefinition] = {}
        views_dir = self._root / "views"
        templates_dir = self._root / "templates"
        if not views_dir.is_dir() or not templates_dir.is_dir():
            raise ResourceError("resources/views and resources/templates are required.")
        for path in sorted(views_dir.rglob("*.json")):
            view = self._parse_view(path)
            if view.id in views:
                raise ResourceError(f"Duplicate view id '{view.id}'.")
            views[view.id] = view
        if entry_view not in views:
            raise ResourceError(f"Entry view '{entry_view}' does not exist.")
        templates = {path.relative_to(templates_dir).as_posix(): path.read_text(encoding="utf-8") for path in templates_dir.rglob("*.txt")}
        for view in views.values():
            if view.template and view.template not in templates:
                raise ResourceError(f"View '{view.id}' references missing template '{view.template}'.")
            try:
                self._jinja.parse(view.inline_text if view.inline_text is not None else templates[view.template or ""])
            except TemplateError as error:
                raise ResourceError(f"Invalid Jinja template for view '{view.id}': {error}") from error
        self._manifest = BotManifest(entry_view=entry_view, start_flow=start_flow)
        self._views = views
        self._templates = templates

    def render(self, view_id: str, variables: Mapping[str, Any]) -> tuple[str, tuple[tuple[ViewButton, ...], ...]]:
        try:
            view = self._views[view_id]
        except KeyError as error:
            raise ResourceError(f"Unknown view '{view_id}'.") from error
        source = view.inline_text if view.inline_text is not None else self._templates[view.template or ""]
        try:
            return self._jinja.from_string(source).render(**variables), view.keyboard
        except TemplateError as error:
            raise ResourceError(f"Failed to render view '{view_id}': {error}") from error

    def _parse_view(self, path: Path) -> ViewDefinition:
        data = self._read_object(path)
        if data.get("schema_version") != 2:
            raise ResourceError(f"{path} must declare schema_version 2.")
        view_id = self._required_string(data, "id", path)
        text = data.get("text")
        if not isinstance(text, dict) or ("inline" in text) == ("template" in text):
            raise ResourceError(f"{path} text must contain exactly one of inline or template.")
        inline = text.get("inline") if isinstance(text.get("inline"), str) else None
        template = text.get("template") if isinstance(text.get("template"), str) else None
        if inline is None and template is None:
            raise ResourceError(f"{path} text must be a non-empty string.")
        keyboard_rows = data.get("keyboard", [])
        if not isinstance(keyboard_rows, list):
            raise ResourceError(f"{path} keyboard must be an array.")
        keyboard: list[tuple[ViewButton, ...]] = []
        for row in keyboard_rows:
            if not isinstance(row, list):
                raise ResourceError(f"{path} keyboard rows must be arrays.")
            buttons: list[ViewButton] = []
            for button in row:
                if not isinstance(button, dict) or not isinstance(button.get("text"), str) or not isinstance(button.get("action"), dict):
                    raise ResourceError(f"{path} contains an invalid keyboard button.")
                action = button["action"]
                action_type = action.get("type")
                if action_type not in {"navigate", "flow.start", "flow.cancel", "flow.event"}:
                    raise ResourceError(f"{path} contains an invalid action type.")
                target = action.get("target")
                if target is not None and not isinstance(target, str):
                    raise ResourceError(f"{path} action target must be a string.")
                if action_type in {"navigate", "flow.start", "flow.event"} and not target:
                    raise ResourceError(f"{path} action '{action_type}' requires a target.")
                buttons.append(ViewButton(button["text"], ViewAction(action_type, target)))
            keyboard.append(tuple(buttons))
        return ViewDefinition(view_id, inline, template, tuple(keyboard))

    @staticmethod
    def _required_string(data: Mapping[str, Any], key: str, path: Path) -> str:
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ResourceError(f"{path} field '{key}' must be a non-empty string.")
        return value.strip()

    @staticmethod
    def _read_object(path: Path) -> dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ResourceError(f"Cannot load JSON resource: {path}") from error
        if not isinstance(data, dict):
            raise ResourceError(f"JSON resource must be an object: {path}")
        return data
