from __future__ import annotations

from telegram.ext import Application

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.background.dispatcher import DefaultTaskDispatcher
from core.background.background_worker import BackgroundWorker
from core.background.recurring_scheduler_worker import RecurringSchedulerWorker
from core.runtime.app_config import AppConfig
from core.runtime.plugins.background.background_service import BackgroundService

from pipubot.background.handlers.handlers import build_task_handlers
from pipubot.background.jobs.bootstrap import bootstrap_system_recurring


def _get_session_maker(app: Application) -> async_sessionmaker[AsyncSession]:
    maker = app.bot_data.get("session_maker")
    if maker is None:
        raise RuntimeError("session_maker not found in app.bot_data.")
    return maker


def build_background_services(app: Application, config: AppConfig) -> list[BackgroundService]:
    session_maker = _get_session_maker(app)

    # 1) Ensure recurring tasks exist
    bootstrap_system_recurring(session_maker)

    # 2) Dispatcher with pipubot handlers
    dispatcher = DefaultTaskDispatcher(
        handlers=build_task_handlers()
    )

    # 3) Workers
    recurring = RecurringSchedulerWorker(session_maker=session_maker)
    worker = BackgroundWorker(session_maker=session_maker, dispatcher=dispatcher)

    return [recurring, worker]