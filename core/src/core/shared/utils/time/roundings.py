from typing import Protocol, runtime_checkable


@runtime_checkable
class EnumNameLike(Protocol):
    @property
    def name(self) -> str: ...


def round_minutes_to_step(
    minutes: int,
    step: int,
    mode: str | EnumNameLike,
) -> int:
    """
    Round minutes to a given step.

    mode:
        "NONE"
        "DOWN"
        "UP"
        "NEAREST"

    Or enum with .name property.
    """

    if step <= 0:
        return minutes

    if minutes <= 0:
        return 0

    mode_name = _normalize_rounding_mode(mode)

    if mode_name == "NONE":
        return minutes

    quotient, remainder = divmod(minutes, step)

    if remainder == 0:
        return minutes

    if mode_name == "DOWN":
        return quotient * step

    if mode_name == "UP":
        return (quotient + 1) * step

    if mode_name == "NEAREST":
        if remainder * 2 >= step:
            return (quotient + 1) * step
        return quotient * step

    raise ValueError(f"Unknown rounding mode: {mode_name}")


def _normalize_rounding_mode(mode: str | EnumNameLike) -> str:
    if isinstance(mode, EnumNameLike):
        return mode.name.upper()

    if isinstance(mode, str):
        return mode.upper()

    raise TypeError(f"Invalid rounding mode type: {type(mode)}")