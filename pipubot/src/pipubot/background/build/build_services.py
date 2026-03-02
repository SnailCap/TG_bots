from __future__ import annotations

import importlib
from telegram.ext import Application

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.background.dispatcher import DefaultTaskDispatcher
from core.background.background_worker import BackgroundWorker
from core.background.recurring_scheduler_worker import RecurringSchedulerWorker
from core.runtime.app_config import AppConfig
from core.runtime.plugins.background.background_service import BackgroundService
from core.background.handler_registry import build_task_handlers
from core.runtime.app_services import AppServices

from pipubot.background.jobs.bootstrap import bootstrap_system_recurring


def _get_session_maker(app: Application) -> async_sessionmaker[AsyncSession]:
    maker = app.bot_data.get("session_maker")
    if maker is None:
        raise RuntimeError("session_maker not found in app.bot_data.")
    return maker


def _get_services(app: Application) -> AppServices:
    services = app.bot_data.get("services")
    if services is None:
        raise RuntimeError("services not found in app.bot_data. Ensure AppFactory.register_handlers() sets it.")
    return services


def _import_handler_modules(config: AppConfig) -> None:
    """
    IMPORTANT:
    Decorator-based registration happens at import time.
    If we don't import handler modules, the registry will be empty.
    """
    modules = getattr(config, "background_handler_modules", None)
    if not modules:
        raise RuntimeError(
            "AppConfig.background_handler_modules is empty. "
            "Provide modules that contain @task_handler registrations."
        )

    for mod in modules:
        importlib.import_module(mod)


def build_background_services(app: Application, config: AppConfig) -> list[BackgroundService]:
    session_maker = _get_session_maker(app)
    services = _get_services(app)

    # 0) Load handler modules (so decorators run and fill registry)
    _import_handler_modules(config)

    # 1) Ensure recurring tasks exist
    bootstrap_system_recurring(session_maker)

    # 2) Dispatcher (now needs services)
    dispatcher = DefaultTaskDispatcher(
        handlers=build_task_handlers(),
        services=services,
    )

    # 3) Workers
    recurring = RecurringSchedulerWorker(session_maker=session_maker)
    worker = BackgroundWorker(session_maker=session_maker, dispatcher=dispatcher)

    return [recurring, worker]