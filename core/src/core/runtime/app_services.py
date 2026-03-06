from __future__ import annotations

from typing import Protocol

from core.interaction.contracts.messenger import Messenger
from core.interaction.contracts.ui_builder import UiBuilder
from core.services.identity.contracts import IdentityProvider
from core.services.notifications.notification_service import NotificationService


class InteractionServices(Protocol):
    ui: UiBuilder
    messenger: Messenger
    notification_service: NotificationService

class AppServices(Protocol):
    interaction: InteractionServices
    identity: IdentityProvider