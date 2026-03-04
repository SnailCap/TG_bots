from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

class TimeRangeError(ValueError):
    pass

@dataclass(frozen=True, slots=True)
class TimeRange:
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        # We do not enforce tz-aware here; that's a separate concern (tz utils).
        if self.end <= self.start:
            raise TimeRangeError("end must be > start")

    @property
    def duration_seconds(self) -> int:
        return int((self.end - self.start).total_seconds())

    @property
    def duration_minutes_floor(self) -> int:
        return max(0, self.duration_seconds // 60)

    @property
    def duration_minutes_ceil(self) -> int:
        secs = self.duration_seconds
        if secs <= 0:
            return 0
        return (secs + 59) // 60

    def overlaps(self, other: "TimeRange") -> bool:
        return self.start < other.end and other.start < self.end

    def intersection(self, other: "TimeRange") -> "TimeRange | None":
        if not self.overlaps(other):
            return None
        return TimeRange(start=max(self.start, other.start), end=min(self.end, other.end))

    def clamp(self, *, min_start: datetime | None = None, max_end: datetime | None = None) -> "TimeRange":
        start = self.start if min_start is None else max(self.start, min_start)
        end = self.end if max_end is None else min(self.end, max_end)
        return TimeRange(start=start, end=end)

    def shift(self, delta: timedelta) -> "TimeRange":
        return TimeRange(start=self.start + delta, end=self.end + delta)
