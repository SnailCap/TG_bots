from __future__ import annotations

import os

from dotenv import load_dotenv

from core.background.build_services import build_background_services
from core.runtime.services.base_runtime_services import BaseAppServices
from pipubot.paths.main_paths import PipubotPaths
from pipubot.domains.tutoring.calendar.oauth_service import GoogleOAuthService
from pipubot.runtime.google_calendar_runtime import GoogleCalendarRuntime
from pipubot.runtime.pipubot_config import PipubotConfig
from pipubot.runtime.pipubot_services import PipubotServices
from pipubot.runtime.secrets import EnvSecretBackend, SecretsService


def build_pipubot_config(*, file: str) -> PipubotConfig:
    paths = PipubotPaths.from_file(file)
    _load_env_file(paths.repo_root)

    return PipubotConfig(
        bot_token=os.environ["BOT_TOKEN"],
        config_root=paths.config_root,
        root_package="pipubot",
        database_url=os.environ["DATABASE_URL"],
        build_background_services=build_background_services,
        recurring_prefix="system.",
        google_default_timeout_s=20.0,
    )


def _load_env_file(repo_root) -> None:
    load_dotenv(repo_root / ".env", override=False)


def build_pipubot_services(
    base: BaseAppServices,
    *,
    config: PipubotConfig,
) -> PipubotServices:
    secrets = SecretsService.from_backend(EnvSecretBackend())
    google_oauth = GoogleOAuthService()
    google_calendar = GoogleCalendarRuntime(
        secrets=secrets,
        google_oauth=google_oauth,
        default_timeout_s=config.google_default_timeout_s,
    )

    return PipubotServices(
        interaction=base.interaction,
        identity=base.identity,
        secrets=secrets,
        google_oauth=google_oauth,
        google_calendar=google_calendar,
    )
