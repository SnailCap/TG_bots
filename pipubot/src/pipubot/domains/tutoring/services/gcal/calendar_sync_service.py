from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.ext.asyncio import AsyncSession

from core.db.transactional import transactional
from core.shared.utils.time import utc_now
from pipubot.domains.tutoring.enums.enums import BillingChargeModel, LessonStatus
from pipubot.domains.tutoring.integrations.google_calendar.calendar_client import (
    CalendarClient,
    CalendarEventsPage,
    CalendarSyncTokenExpired,
)
from pipubot.domains.tutoring.repositories.calendar_source_repository import (
    get_calendar_source,
    set_last_synced_at,
    set_sync_token,
    upsert_calendar_source,
)
from pipubot.domains.tutoring.repositories.lesson_repository import upsert_lesson_from_gcal_event
from pipubot.domains.tutoring.repositories.student_repository import get_student_by_id
from pipubot.domains.tutoring.services.gcal.student_title_match import (
    StudentResolveResult,
    resolve_student_id_by_event_title,
)


def _map_status(ev_status: str) -> LessonStatus:
    return LessonStatus.CANCELED if ev_status == "cancelled" else LessonStatus.PLANNED


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _duration_minutes_floor(start: datetime, end: datetime) -> int:
    seconds = (end - start).total_seconds()
    return int(seconds // 60)


def _calc_planned_charge_simple(
    *,
    charge_model: BillingChargeModel,
    duration_min: int,
    rate: Decimal,
) -> Decimal:
    """
    Planned pricing used during GCAL sync as a "snapshot":
    - FIXED -> charge == rate
    - otherwise -> PER_HOUR by duration (simple, predictable)
    """
    if charge_model == BillingChargeModel.FIXED:
        return _money(rate)

    hours = Decimal(duration_min) / Decimal(60)
    return _money(rate * hours)


def _safe_event_text(value: str | None, *, is_cancelled: bool) -> str | None:
    return None if is_cancelled else value


async def _resolve_student_snapshot(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    title: str | None,
    start_at: datetime,
    end_at: datetime,
    is_cancelled: bool,
) -> tuple[int | None, str, Decimal | None, Decimal | None]:
    """
    Resolve student and planned financial snapshot for the lesson.

    Returns:
        (student_id, currency, planned_rate_snapshot, planned_charge_amount)
    """
    match_result: StudentResolveResult = await resolve_student_id_by_event_title(
        session,
        tutor_user_id=tutor_user_id,
        title=title,
    )
    student_id = match_result.student_id if match_result.kind == "matched" else None

    currency = "EUR"
    planned_rate_snapshot: Decimal | None = None
    planned_charge_amount: Decimal | None = None

    if student_id is None or is_cancelled:
        return student_id, currency, planned_rate_snapshot, planned_charge_amount

    student = await get_student_by_id(
        session,
        tutor_user_id=tutor_user_id,
        student_id=student_id,
    )
    if student is None:
        return student_id, currency, planned_rate_snapshot, planned_charge_amount

    currency = student.default_currency or "EUR"

    if student.default_rate is not None:
        planned_rate_snapshot = student.default_rate
        duration_min = _duration_minutes_floor(start_at, end_at)
        planned_charge_amount = _calc_planned_charge_simple(
            charge_model=student.charge_model,
            duration_min=duration_min,
            rate=student.default_rate,
        )

    return student_id, currency, planned_rate_snapshot, planned_charge_amount


async def _apply_events(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    calendar_id: str,
    page: CalendarEventsPage,
) -> None:
    for ev in page.items:
        is_cancelled = ev.status == "cancelled"

        student_id, currency, planned_rate_snapshot, planned_charge_amount = await _resolve_student_snapshot(
            session,
            tutor_user_id=tutor_user_id,
            title=ev.summary,
            start_at=ev.start_at,
            end_at=ev.end_at,
            is_cancelled=is_cancelled,
        )

        await upsert_lesson_from_gcal_event(
            session,
            tutor_user_id=tutor_user_id,
            google_calendar_id=calendar_id,
            google_event_id=ev.google_event_id,
            start_at=ev.start_at,
            end_at=ev.end_at,
            status=_map_status(ev.status),
            google_updated_at=ev.updated_at,
            google_ical_uid=ev.ical_uid,
            google_recurring_event_id=ev.recurring_event_id,
            title=_safe_event_text(ev.summary, is_cancelled=is_cancelled),
            description=_safe_event_text(ev.description, is_cancelled=is_cancelled),
            student_id=student_id,
            currency=currency,
            planned_rate_snapshot=planned_rate_snapshot,
            planned_charge_amount=planned_charge_amount,
        )


@transactional
async def sync_calendar_window(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    calendar_id: str,
    client: CalendarClient,
    horizon_days: int = 60,
    backfill_days: int = 7,
    now: datetime | None = None,
) -> None:
    now = now or utc_now()
    time_min = now - timedelta(days=backfill_days)
    time_max = now + timedelta(days=horizon_days)

    source = await upsert_calendar_source(session, tutor_user_id=tutor_user_id, calendar_id=calendar_id)
    source.window_days = horizon_days

    page = await client.list_events_window(
        calendar_id=calendar_id,
        time_min=time_min,
        time_max=time_max,
        show_deleted=True,
    )

    await _apply_events(session, tutor_user_id=tutor_user_id, calendar_id=calendar_id, page=page)
    await set_sync_token(session, tutor_user_id=tutor_user_id, calendar_id=calendar_id, sync_token=page.next_sync_token)
    await set_last_synced_at(session, tutor_user_id=tutor_user_id, calendar_id=calendar_id, last_synced_at=now)


@transactional
async def sync_calendar_delta(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    calendar_id: str,
    client: CalendarClient,
    now: datetime | None = None,
) -> None:
    now = now or utc_now()

    source = await get_calendar_source(session, tutor_user_id=tutor_user_id, calendar_id=calendar_id)
    if not source or not source.sync_token:
        return

    page = await client.list_events_delta(
        calendar_id=calendar_id,
        sync_token=source.sync_token,
        show_deleted=True,
    )

    await _apply_events(session, tutor_user_id=tutor_user_id, calendar_id=calendar_id, page=page)

    await set_sync_token(session, tutor_user_id=tutor_user_id, calendar_id=calendar_id, sync_token=page.next_sync_token)
    await set_last_synced_at(session, tutor_user_id=tutor_user_id, calendar_id=calendar_id, last_synced_at=now)


@transactional
async def sync_calendar(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    calendar_id: str,
    client: CalendarClient,
    horizon_days: int = 60,
    backfill_days: int = 7,
    now: datetime | None = None,
) -> None:
    """
    Periodic sync entrypoint:

    - no sync_token -> window sync
    - has sync_token -> delta sync
    - token expired (410 Gone) -> window sync again
    """
    now = now or utc_now()

    source = await get_calendar_source(session, tutor_user_id=tutor_user_id, calendar_id=calendar_id)
    if not source or not source.sync_token:
        await sync_calendar_window(
            session,
            tutor_user_id=tutor_user_id,
            calendar_id=calendar_id,
            client=client,
            horizon_days=horizon_days,
            backfill_days=backfill_days,
            now=now,
        )
        return

    try:
        await sync_calendar_delta(
            session,
            tutor_user_id=tutor_user_id,
            calendar_id=calendar_id,
            client=client,
            now=now,
        )
    except CalendarSyncTokenExpired:
        await sync_calendar_window(
            session,
            tutor_user_id=tutor_user_id,
            calendar_id=calendar_id,
            client=client,
            horizon_days=horizon_days,
            backfill_days=backfill_days,
            now=now,
        )