from dataclasses import dataclass

from core.interaction.contracts.messenger import Messenger
from core.interaction.contracts.ui_builder import UiBuilder
from core.services.identity.contracts import IdentityProvider
from core.services.notifications.notification_service import NotificationService
from pipubot.domains.tutoring.services.gcal.google_oauth_service import GoogleOAuthService
from pipubot.runtime.secrets import SecretsService


@dataclass(frozen=True, slots=True)
class DefaultInteractionServices:
    ui: UiBuilder
    messenger: Messenger
    notification_service: NotificationService


@dataclass(frozen=True, slots=True)
class DefaultAppServices:
    interaction: DefaultInteractionServices
    identity: IdentityProvider
    secrets: SecretsService
    google_oauth: GoogleOAuthService
