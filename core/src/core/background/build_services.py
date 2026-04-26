from __future__ import annotations

from typing import Any

from telegram.ext import Application

from core.background.background_worker import BackgroundWorker
from core.background.bootstrap import bootstrap_registered_recurring
from core.background.dispatcher import DefaultTaskDispatcher
from core.background.handler_registry import build_handler_entries
from core.background.recurring_scheduler_worker import RecurringSchedulerWorker
from core.runtime.app_config import AppConfig
from core.runtime.app_services import AppServices
from core.runtime.context.runtime_context import RuntimeContext
from core.runtime.plugins.background.background_service import BackgroundService


def _get_session_maker(app: Application):
    runtime = RuntimeContext(app)
    if not runtime.has_session_maker():
        raise RuntimeError("DB session maker is not available in runtime context.")
    return runtime.get_session_maker()


def _get_services(app: Application) -> AppServices:
    runtime = RuntimeContext(app)
    if not runtime.has_services():
        raise RuntimeError("Runtime services are not available in runtime context.")
    return runtime.get_services()


def build_background_services(app: Any, config: AppConfig) -> list[BackgroundService]:
    assert isinstance(app, Application)

    session_maker = _get_session_maker(app)
    services = _get_services(app)

    if getattr(config, "bootstrap_recurring", True):
        prefix = getattr(config, "recurring_prefix", "system.")
        bootstrap_registered_recurring(session_maker, prefix=prefix)

    dispatcher = DefaultTaskDispatcher(
        handler_entries=build_handler_entries(),
        services=services,
    )

    recurring = RecurringSchedulerWorker(session_maker=session_maker)
    worker = BackgroundWorker(session_maker=session_maker, dispatcher=dispatcher)

    return [recurring, worker]