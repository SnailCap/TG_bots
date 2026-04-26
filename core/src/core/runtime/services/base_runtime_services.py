from __future__ import annotations

from dataclasses import dataclass

from core.interaction.contracts.messenger import Messenger
from core.interaction.contracts.ui_builder import UiBuilder
from core.services.identity.contracts import IdentityProvider
from core.services.notifications.notification_service import NotificationService


@dataclass(frozen=True, slots=True)
class BaseInteractionServices:
    ui: UiBuilder
    messenger: Messenger
    notification_service: NotificationService


@dataclass(frozen=True, slots=True)
class BaseAppServices:
    interaction: BaseInteractionServices
    identity: IdentityProvider