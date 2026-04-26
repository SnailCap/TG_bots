from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from core.interaction.config import ConfigLoader
from core.interaction.config import ResourcePaths
from core.interaction.ui.templating.jinja_text_renderer import JinjaTextRenderer
from core.interaction.ui.templating.text_renderer import TextRenderer
from core.interaction.ui.binding import UiClassResolver
from .renderable_builder import RenderableBuilder

from ..keyboard import ButtonBuilder
from ..keyboard import KeyboardBuilder

from ..components.page.base_page import Page
from core.interaction.ui.components.process.base.base_step import Step
from ..components.notification.base_notification import Notification


class UiBuildError(RuntimeError):
    pass


class UnknownUiKey(UiBuildError):
    pass


@dataclass(slots=True)
class UiBuilder:
    paths: ResourcePaths
    loader: ConfigLoader
    renderable_builder: RenderableBuilder
    resolver: UiClassResolver = field(default_factory=UiClassResolver.default)
    text_renderer: TextRenderer = field(default_factory=JinjaTextRenderer)

    _keyboard_builder: Optional[KeyboardBuilder] = field(default=None, init=False, repr=False)

    def build_page(self, key: str) -> Page:
        cfg = self._pages_index().require(key)
        dto = self.renderable_builder.build_from_config(
            cfg,
            text_root_dir=self._text_root("pages"),
            key=key,
        )

        cls = self.resolver.resolve_page(key, Page)

        return cls(
            text_template=dto.text_template,
            inline_keyboard_template=None,
            keyboard_builder=self._get_keyboard_builder(),
            text_renderer=self.text_renderer,
            default_keyboard_layout=dto.keyboard_layout,
        )

    def build_step(self, key: str) -> Step:
        cfg = self._steps_index().require(key)
        dto = self.renderable_builder.build_from_config(
            cfg,
            text_root_dir=self._text_root("steps"),
            key=key,
        )

        cls = self.resolver.resolve_step(key, Step)

        return cls(
            text_template=dto.text_template,
            inline_keyboard_template=None,
            keyboard_builder=self._get_keyboard_builder(),
            text_renderer=self.text_renderer,
            default_keyboard_layout=dto.keyboard_layout,
        )

    def build_notification(self, key: str) -> Notification:
        cfg = self._notifications_index().require(key)
        dto = self.renderable_builder.build_from_config(
            cfg,
            text_root_dir=self._text_root("notifications"),
            key=key,
        )

        cls = self.resolver.resolve_notification(key, Notification)

        parse_mode = cfg.get("parse_mode", "HTML")
        html_escape_variables = bool(cfg.get("html_escape_variables", False))

        return cls(
            text_template=dto.text_template,
            inline_keyboard_template=None,
            keyboard_builder=self._get_keyboard_builder(),
            text_renderer=self.text_renderer,
            default_keyboard_layout=dto.keyboard_layout,
            html_escape_variables=html_escape_variables,
            parse_mode=parse_mode,
        )

    def _get_keyboard_builder(self) -> KeyboardBuilder:
        if self._keyboard_builder is not None:
            return self._keyboard_builder

        button_builder = ButtonBuilder(loader=self.loader)
        self._keyboard_builder = KeyboardBuilder(button_builder=button_builder)
        return self._keyboard_builder

    def _pages_index(self):
        return self.loader.load_pages()

    def _steps_index(self):
        return self.loader.load_steps()

    def _notifications_index(self):
        return self.loader.load_notifications()

    def _text_root(self, entity: str) -> Path:
        return self.paths.root / "text" / entity