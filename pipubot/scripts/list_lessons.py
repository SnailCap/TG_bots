from __future__ import annotations

import asyncio
import os
from datetime import timezone

from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Регистрируем модели
import core.db.models  # noqa: F401
import pipubot.domains.tutoring.models  # noqa: F401

from pipubot.domains.tutoring.models.lesson import TutoringLesson


def fmt_dt(dt):
    if not dt:
        return "-"
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M")


async def main():
    load_dotenv()

    database_url = os.environ["DATABASE_URL"]
    tutor_user_id = int(os.environ["KONSTANTIN_USER_ID"])

    engine = create_async_engine(database_url, future=True)
    session = async_sessionmaker(engine, expire_on_commit=False)

    async with session() as session:
        stmt = (
            select(TutoringLesson)
            .where(TutoringLesson.tutor_user_id == tutor_user_id)
            .order_by(TutoringLesson.start_at.asc())
        )

        lessons = (await session.execute(stmt)).scalars().all()

    await engine.dispose()

    if not lessons:
        print("Нет уроков.")
        return

    print(f"\nУроки (tutor_user_id={tutor_user_id}):\n")

    for l in lessons:
        print("—" * 60)
        print(f"ID:        {l.id}")
        print(f"Начало:    {fmt_dt(l.start_at)}")
        print(f"Конец:     {fmt_dt(l.end_at)}")
        print(f"Статус:    {l.status}")
        print(f"Ученик:    {l.student_id}")
        print(f"Сумма:     {l.charge_amount} {l.currency}")
        print(f"Название:  {l.title}")
        print(f"GCal ID:   {l.google_event_id}")
        print(f"tutor_id:  {l.tutor_user_id}")

    print("\nГотово.\n")


if __name__ == "__main__":
    asyncio.run(main())