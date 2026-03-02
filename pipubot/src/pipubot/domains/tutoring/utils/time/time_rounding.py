from __future__ import annotations

from pipubot.domains.tutoring.models.enums import RoundingMode


def round_minutes(minutes: int, step: int, mode: RoundingMode) -> int:
    if step <= 0 or mode == RoundingMode.NONE:
        return minutes
    if minutes <= 0:
        return 0

    q, r = divmod(minutes, step)
    if r == 0:
        return minutes

    if mode == RoundingMode.DOWN:
        return q * step
    if mode == RoundingMode.UP:
        return (q + 1) * step
    if mode == RoundingMode.NEAREST:
        return (q + (1 if r * 2 >= step else 0)) * step

    return minutes