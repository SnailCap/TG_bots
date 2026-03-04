from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from core.db import Base

# Регистрируем все модели
import core.db.models  # noqa: F401
import pipubot.domains.tutoring.models  # noqa: F401

from core.db.repositories.user_repository import create_or_update_user
from core.interaction.types import UserRole


async def _reset_full(url: str) -> None:
    print(f"[db-reset] Connecting to {url}")
    engine = create_async_engine(url, future=True)

    # ---- RESET SCHEMA ----
    async with engine.begin() as conn:
        print("[db-reset] Dropping schema public...")
        await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))

        print("[db-reset] Creating schema public...")
        await conn.execute(text("CREATE SCHEMA public"))

        print("[db-reset] Creating tables from models...")
        await conn.run_sync(Base.metadata.create_all)

    # ---- SEED USER ----
    tutor_id_str = os.environ.get("KONSTANTIN_USER_ID")
    if not tutor_id_str:
        raise RuntimeError("KONSTANTIN_USER_ID not found in environment.")

    tutor_telegram_id = int(tutor_id_str)

    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async with session_maker() as session:
        print(f"[db-reset] Seeding user telegram_id={tutor_telegram_id}")

        await create_or_update_user(
            session,
            telegram_id=tutor_telegram_id,
            role=UserRole.ADMIN,  # можно заменить на ADMIN если нужно
        )

        await session.commit()

    await engine.dispose()
    print("[db-reset] Done.")


def reset_full_database() -> None:
    load_dotenv()  # загружаем .env
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL not found in environment.")

    asyncio.run(_reset_full(db_url))


if __name__ == "__main__":
    reset_full_database()