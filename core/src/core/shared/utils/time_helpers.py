from datetime import datetime, timezone


def utcnow(): return datetime.now(timezone.utc)

def to_utc_dt(timestamp: int | None) -> datetime | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)