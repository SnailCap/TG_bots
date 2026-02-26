from __future__ import annotations

import asyncio
import importlib
import logging
import os
import sys
from functools import partial
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from telegram.ext import Application

from core.src.db.providers.sqlalchemy_session_provider import SqlAlchemySessionProvider
from core.src.interaction.adapters.ptb.update_dispatcher import UpdateDispatcher
from core.src.interaction.config.api import build_config_loader
from core.src.interaction.config.paths import ResourcePaths
from core.src.interaction.routing.user_input_router import UserInputRouter
from core.src.interaction.ui.builders.renderable_builder import RenderableBuilder
from core.src.interaction.ui.builders.ui_builder import PtbUiBuilder
from core.src.runtime import AppConfig, run_app
from core.src.services.identity.provider import DbIdentityProvider


def build_application(config: AppConfig) -> Application:
    return Application.builder().token(config.bot_token).build()


def _import_ui_binding_modules(config: AppConfig) -> None:
    """
    Гарантируем, что UI binding-модули импортированы ДО старта polling.
    Это снижает риск, что первый апдейт придёт раньше, чем UiBindingsPlugin успеет отработать.
    """
    for mod in config.ui_binding_modules:
        importlib.import_module(mod)


def build_dispatcher(config: AppConfig) -> UpdateDispatcher:
    if not config.database_url:
        raise RuntimeError(
            "DATABASE_URL is not set. Please set env var DATABASE_URL (use a placeholder in docs)."
        )

    _import_ui_binding_modules(config)

    # --- UI/config ---
    paths = ResourcePaths.from_root(config.config_root).normalized()
    loader = build_config_loader(config.config_root)

    renderable_builder = RenderableBuilder(loader=loader)
    ui_builder = PtbUiBuilder(paths=paths, loader=loader, renderable_builder=renderable_builder)
    router = UserInputRouter(ui=ui_builder)

    # --- DB ---
    engine = create_async_engine(
        config.database_url,
        echo=config.database_echo,
    )
    session_maker: async_sessionmaker[AsyncSession] = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )
    session_provider = SqlAlchemySessionProvider(session_maker=session_maker)

    # --- Identity ---
    identity_provider = DbIdentityProvider()

    return UpdateDispatcher(
        router=router,
        session_provider=session_provider,
        identity_provider=identity_provider,
    )


def register_handlers(app: Application, dispatcher: UpdateDispatcher) -> None:
    dispatcher.register_handlers(app)


def main() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        force=True,
    )

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    config = AppConfig(
        bot_token=os.environ["BOT_TOKEN"],
        config_root=str(Path(__file__).resolve().parent.parent / "resources" / "config"),
        ui_binding_modules=("pipubot.src.ui.components",),
        database_url=os.environ.get("DATABASE_URL"),
    )

    dispatcher = build_dispatcher(config)

    run_app(
        config,
        build_application=build_application,
        register_handlers=partial(register_handlers, dispatcher=dispatcher),
    )


if __name__ == "__main__":
    main()
