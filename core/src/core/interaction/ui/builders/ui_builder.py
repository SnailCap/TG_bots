from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from core.interaction.config.loader import ConfigLoader
from core.interaction.config.paths import ResourcePaths
from core.interaction.ui.binding import UiClassResolver
from core.interaction.ui.builders.renderable_builder import RenderableBuilder

from core.interaction.ui.builders.button_builder import ButtonBuilder
from core.interaction.ui.builders.keyboard_builder import KeyboardBuilder

from core.interaction.ui.components.pages.page import Page
from core.interaction.ui.components.process.base_step import Step
from core.interaction.ui.components.notifications.base import Notification


class UiBuildError(RuntimeError):
    pass


class UnknownUiKey(UiBuildError):
    pass


@dataclass(slots=True)
class PtbUiBuilder:
    """
    Универсальный билдер сущностей UI.

    Отвечает за:
    - load cfg by key (через ConfigLoader)
    - сборку renderable DTO (text + keyboard_layout) через RenderableBuilder
    - выбор python-класса через UiClassResolver (custom или базовый)
    - создание инстанса сущности

    Важно:
    - KeyboardBuilder создаётся внутри, т.к. реализация одна и DI не нужен.
    """

    paths: ResourcePaths
    loader: ConfigLoader
    renderable_builder: RenderableBuilder
    resolver: UiClassResolver = field(default_factory=UiClassResolver.default)

    _keyboard_builder: Optional[KeyboardBuilder] = field(default=None, init=False, repr=False)

    # -------------------------
    # public API
    # -------------------------
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
            default_keyboard_layout=dto.keyboard_layout,
            html_escape_variables=html_escape_variables,
            parse_mode=parse_mode,
        )

    # -------------------------
    # internals: build dependencies (no DI)
    # -------------------------
    def _get_keyboard_builder(self) -> KeyboardBuilder:
        """
        Ленивая сборка:
        - ButtonBuilder -> KeyboardBuilder

        Почему так:
        - реализации 1 штука
        - зависимости тривиальные
        - PtbUiBuilder — composition root для UI, пусть и собирает.
        """
        if self._keyboard_builder is not None:
            return self._keyboard_builder

        button_builder = ButtonBuilder(loader=self.loader)
        self._keyboard_builder = KeyboardBuilder(button_builder=button_builder)
        return self._keyboard_builder

    # -------------------------
    # internals: indexes
    # -------------------------
    def _pages_index(self):
        return self.loader.load_pages()

    def _steps_index(self):
        return self.loader.load_steps()

    def _notifications_index(self):
        return self.loader.load_notifications()

    # -------------------------
    # internals: text roots
    # -------------------------
    def _text_root(self, entity: str) -> Path:
        """
        Контракт: текстовые шаблоны лежат относительно config_root/text/<entity>/
        Пример: config_root/text/pages/home_page.txt
        """
        return self.paths.root / "text" / entity