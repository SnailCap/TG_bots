from __future__ import annotations

from typing import Protocol

from core.interaction.contracts.messenger import Messenger
from core.interaction.contracts.ui_builder import UiBuilder
from core.services.identity.contracts import IdentityProvider


class InteractionServices(Protocol):
    @property
    def ui(self) -> UiBuilder: ...

    @property
    def messenger(self) -> Messenger: ...


class AppServices(Protocol):
    @property
    def interaction(self) -> InteractionServices: ...

    @property
    def identity(self) -> IdentityProvider: ...