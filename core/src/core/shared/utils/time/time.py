from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pendulum

DEFAULT_TIMEZONE_NAME = "Europe/Tallinn"
UTC_TIMEZONE_NAME = "UTC"


@dataclass(frozen=True, slots=True)
class TimeWindow:
    start: datetime
    end: datetime


def utc_now() -> datetime:
    """
    Return current time in UTC (tz-aware).
    """
    return pendulum.now(UTC_TIMEZONE_NAME)


def now_in_timezone(timezone_name: str = DEFAULT_TIMEZONE_NAME) -> datetime:
    """
    Return current time in a specific timezone (tz-aware).
    """
    return pendulum.now(timezone_name)


def ensure_timezone_aware(
    dt: datetime,
    *,
    default_timezone_name: str = DEFAULT_TIMEZONE_NAME,
) -> datetime:
    """
    Ensure datetime is timezone-aware.

    If dt is naive, interpret it in the default timezone.
    """
    if dt.tzinfo is not None:
        return dt

    tz = pendulum.timezone(default_timezone_name)

    # Interpret naive datetime as being in default timezone.
    return pendulum.datetime(
        dt.year,
        dt.month,
        dt.day,
        dt.hour,
        dt.minute,
        dt.second,
        dt.microsecond,
        tz=tz,
    )


def require_timezone_aware(dt: datetime) -> datetime:
    """
    Require tz-aware datetime; raise if dt is naive.

    Use in places where naive datetime is considered a bug.
    """
    if dt.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return dt


def convert_to_timezone(
    dt: datetime,
    timezone_name: str,
    *,
    default_timezone_name: str = DEFAULT_TIMEZONE_NAME,
) -> datetime:
    """
    Convert datetime to a specific timezone.

    If dt is naive, interpret it in default timezone first.
    """
    aware = ensure_timezone_aware(dt, default_timezone_name=default_timezone_name)
    return pendulum.instance(aware).in_timezone(timezone_name)


def convert_to_utc(
    dt: datetime,
    *,
    default_timezone_name: str = DEFAULT_TIMEZONE_NAME,
) -> datetime:
    """
    Convert datetime to UTC.

    If dt is naive, interpret it in default timezone first.
    """
    return convert_to_timezone(
        dt,
        UTC_TIMEZONE_NAME,
        default_timezone_name=default_timezone_name,
    )


def to_default_timezone(
    dt: datetime,
    *,
    default_timezone_name: str = DEFAULT_TIMEZONE_NAME,
) -> datetime:
    """
    Convert datetime to DEFAULT_TIMEZONE_NAME.

    If dt is naive, interpret it in default timezone first (no-op).
    """
    return convert_to_timezone(
        dt,
        default_timezone_name,
        default_timezone_name=default_timezone_name,
    )


def upcoming_window_utc(minutes: int) -> TimeWindow:
    """
    Return [now_utc, now_utc + minutes] window in UTC.
    """
    if minutes <= 0:
        now = utc_now()
        return TimeWindow(start=now, end=now)

    start = utc_now()
    end = pendulum.instance(start).add(minutes=minutes)
    return TimeWindow(start=start, end=end)


def format_time_hm(
    dt: datetime,
    *,
    timezone_name: str = DEFAULT_TIMEZONE_NAME,
    default_timezone_name: str = DEFAULT_TIMEZONE_NAME,
) -> str:
    """
    Format time as HH:mm in a target timezone.

    If dt is naive, interpret it in default timezone first.
    """
    local = convert_to_timezone(
        dt,
        timezone_name,
        default_timezone_name=default_timezone_name,
    )
    return pendulum.instance(local).format("HH:mm")