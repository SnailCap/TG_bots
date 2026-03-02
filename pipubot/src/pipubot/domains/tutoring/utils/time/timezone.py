from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def ensure_aware(dt: datetime, *, default_tz: str = "Europe/Tallinn") -> datetime:
    """
    If dt is naive, attach the default tz (no conversion).
    If dt is aware, return as-is.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=ZoneInfo(default_tz))
    return dt


def to_utc(dt: datetime, *, default_tz: str = "Europe/Tallinn") -> datetime:
    """
    Convert dt to UTC. If dt is naive, interpret it in default_tz first.
    """
    dt = ensure_aware(dt, default_tz=default_tz)
    return dt.astimezone(timezone.utc)