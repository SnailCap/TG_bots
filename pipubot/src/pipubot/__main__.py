from __future__ import annotations

import logging

from core.runtime.builders.bot_runtime_builder import BotRuntimeBuilder
from core.services.identity.provider import DbIdentityProvider
from pipubot.runtime.pipubot_runtime_setup import (
    build_pipubot_config,
    build_pipubot_services,
)
from scripts.reset_database import reset_full_database


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        force=True,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def main() -> None:
    _setup_logging()
    reset_full_database()
    config = build_pipubot_config(file=__file__)

    runtime = (
        BotRuntimeBuilder(config)
        .with_ptb()
        .with_standard_interaction()
        .with_identity(DbIdentityProvider())
        .extend_services(lambda base: build_pipubot_services(base, config=config))
        .with_runtime_services()
        .with_plugins_from_config()
        .with_dispatcher()
        .build()
    )

    runtime.run()


if __name__ == "__main__":
    main()
