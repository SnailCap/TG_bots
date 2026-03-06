from __future__ import annotations

from typing import Any

from telegram.ext import Application
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.background.background_worker import BackgroundWorker
from core.background.bootstrap import bootstrap_registered_recurring
from core.background.dispatcher import DefaultTaskDispatcher
from core.background.handler_registry import build_handler_entries
from core.background.recurring_scheduler_worker import RecurringSchedulerWorker
from core.runtime.app_config import AppConfig
from core.runtime.app_services import AppServices
from core.runtime.plugins.background.background_service import BackgroundService

BOT_DATA_SESSION_MAKER = "session_maker"
BOT_DATA_SERVICES = "services"


def _get_session_maker(app: Application) -> async_sessionmaker[AsyncSession]:
    maker = app.bot_data.get(BOT_DATA_SESSION_MAKER)
    if maker is None:
        raise RuntimeError(f"{BOT_DATA_SESSION_MAKER} not found in app.bot_data.")
    return maker


def _get_services(app: Application) -> AppServices:
    services = app.bot_data.get(BOT_DATA_SERVICES)
    if services is None:
        raise RuntimeError(
            f"{BOT_DATA_SERVICES} not found in app.bot_data. Ensure AppFactory.register_handlers() sets it.")
    return services


def build_background_services(app: Any, config: AppConfig) -> list[BackgroundService]:
    # app приходит как Any из плагина, но фактически это PTB Application
    assert isinstance(app, Application)

    session_maker = _get_session_maker(app)
    services = _get_services(app)

    # 1) bootstrap recurring (из декораторов)
    if getattr(config, "bootstrap_recurring", True):
        prefix = getattr(config, "recurring_prefix", "system.")
        bootstrap_registered_recurring(session_maker, prefix=prefix)

    # 2) dispatcher (policy/only_recurring уже в handler_entries)
    dispatcher = DefaultTaskDispatcher(
        handler_entries=build_handler_entries(),
        services=services,
    )

    # 3) workers
    recurring = RecurringSchedulerWorker(session_maker=session_maker)
    worker = BackgroundWorker(session_maker=session_maker, dispatcher=dispatcher)

    return [recurring, worker]
