import os
import asyncio
import httpx
from dotenv import load_dotenv

from pipubot.domains.tutoring.integrations.google_calendar.google_calendar_client import (
    GoogleCalendarClient,
    GoogleCalendarClientConfig,
)
from pipubot.domains.tutoring.services.calendar.calendar_sync_service import sync_calendar

from core.shared.utils.session_helper import create_session_maker, create_engine
import core.db.models  # noqa: F401  # регистрирует users в Base.metadata
import pipubot.domains.tutoring.models  # noqa: F401  # регистрирует tutoring таблицы

load_dotenv()

async def refresh_access_token(
    *,
    client_id: str,
    client_secret: str,
    refresh_token: str,
) -> str:
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["access_token"]


async def main() -> None:
    calendar_id = os.environ.get("GCAL_CALENDAR_ID", "primary")
    tutor_user_id = int(os.environ["KONSTANTIN_USER_ID"])
    database_url = os.environ["DATABASE_URL"]

    # OAuth credentials
    client_id = os.environ["GCAL_CLIENT_ID"]
    client_secret = os.environ["GCAL_CLIENT_SECRET"]
    refresh_token = os.environ["GCAL_REFRESH_TOKEN"]

    # Получаем свежий access_token
    access_token = await refresh_access_token(
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
    )

    client = GoogleCalendarClient(
        GoogleCalendarClientConfig(access_token=access_token)
    )

    engine = create_engine(database_url)
    async_session_maker = create_session_maker(engine)

    async with async_session_maker() as session:
        await sync_calendar(
            session,
            tutor_user_id=tutor_user_id,
            calendar_id=calendar_id,
            client=client,
            horizon_days=60,
            backfill_days=7,
        )

    print("Calendar sync finished successfully.")


if __name__ == "__main__":
    asyncio.run(main())