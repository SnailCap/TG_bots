from __future__ import annotations

import asyncio
import os
import sys

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

from core.db import Base
import core.db.models  # noqa: F401


if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def _reset_full(url: str) -> None:
    print(f"[db-reset] Connecting to {url}")
    engine = create_async_engine(url, future=True)

    async with engine.begin() as conn:
        print("[db-reset] Dropping schema public...")
        await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))

        print("[db-reset] Creating schema public...")
        await conn.execute(text("CREATE SCHEMA public"))

        print("[db-reset] Creating tables from models...")
        await conn.run_sync(Base.metadata.create_all)

    await engine.dispose()
    print("[db-reset] Done.")


def reset_full_database() -> None:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL not found in environment.")
    asyncio.run(_reset_full(db_url))


if __name__ == "__main__":
    reset_full_database()