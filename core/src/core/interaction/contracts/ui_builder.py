from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable, Optional

from telegram import InlineKeyboardMarkup

from core.interaction.ui.components.pages.page import Page
from core.interaction.ui.components.process.base_step import Step
from core.interaction.ui.components.notifications.base import Notification


@dataclass(frozen=True, slots=True)
class RenderableDTO:
    text_template: str
    keyboard_template: Optional[InlineKeyboardMarkup]


@runtime_checkable
class UiBuilder(Protocol):
    """
    Контракт "универсального билдера UI сущностей".

    Реализация должна:
    - уметь построить Page/Step/Notification по key
    - возвращать конкретные инстансы сущностей (включая кастомные классы через resolver)
    """

    def build_page(self, key: str) -> Page: ...
    def build_step(self, key: str) -> Step: ...
    def build_notification(self, key: str) -> Notification: ...