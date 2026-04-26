from __future__ import annotations

import asyncio
import os
from decimal import Decimal

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from core.db import Base

import core.db.models  # noqa: F401
import core.db.models.sent_notification  # noqa: F401
import pipubot.domains.helper.models  # noqa: F401
import pipubot.domains.tutoring.models  # noqa: F401

from core.db.repositories.user_repository import create_or_update_user
from core.interaction.types import UserRole

from pipubot.domains.tutoring.enums.payment import BillingChargeModel, RoundingMode
from pipubot.domains.tutoring.models.student import TutoringStudent


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
            role=UserRole.ADMIN,
        )

        # ---- SEED TEST STUDENT ----
        student = TutoringStudent(
            tutor_user_id=tutor_telegram_id,
            user_telegram_id=None,
            full_name="Ризо",
            default_currency="EUR",
            default_rate=Decimal("25.00"),
            charge_model=BillingChargeModel.PER_HOUR,
            rounding_minutes=5,
            rounding_mode=RoundingMode.NEAREST,
            min_billable_minutes=0,

            late_cancel_fee_percent=0,
            no_show_fee_percent=0,

            timezone="Europe/Tallinn",
        )

        session.add(student)

        await session.commit()
        print(f"[db-reset] Seeded student id={student.id} full_name={student.full_name}")

    await engine.dispose()
    print("[db-reset] Done.")


def reset_full_database() -> None:
    load_dotenv()
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL not found in environment.")

    asyncio.run(_reset_full(db_url))


if __name__ == "__main__":
    reset_full_database()
