from dataclasses import dataclass

from core.runtime.app_services import AppServices, InteractionServices
from core.interaction.contracts.messenger import Messenger
from core.interaction.contracts.ui_builder import UiBuilder
from core.services.identity.contracts import IdentityProvider
from core.services.notification_service import NotificationService


@dataclass(frozen=True, slots=True)
class DefaultInteractionServices(InteractionServices):
    ui: UiBuilder
    messenger: Messenger
    notification_service: NotificationService


@dataclass(frozen=True, slots=True)
class DefaultAppServices(AppServices):
    interaction: DefaultInteractionServices
    identity: IdentityProvider