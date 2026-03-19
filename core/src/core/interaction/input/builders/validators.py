from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Callable, TypeVar

ObjectT = TypeVar("ObjectT")
ValueT = TypeVar("ValueT")

Validator = Callable[[ObjectT, ValueT | None], list[str]]


def compose_validators(
    *validators: Validator[ObjectT, ValueT],
) -> Validator[ObjectT, ValueT]:
    def validate(obj: ObjectT, value: ValueT | None) -> list[str]:
        errors: list[str] = []
        for validator in validators:
            errors.extend(validator(obj, value))
        return errors

    return validate


def positive_decimal(
    message: str = "Значение должно быть больше 0.",
) -> Validator[ObjectT, Decimal]:
    def validate(_: ObjectT, value: Decimal | None) -> list[str]:
        if value is None:
            return []
        if value <= 0:
            return [message]
        return []

    return validate


def positive_int(
    message: str = "Значение должно быть больше 0.",
) -> Validator[ObjectT, int]:
    def validate(_: ObjectT, value: int | None) -> list[str]:
        if value is None:
            return []
        if value <= 0:
            return [message]
        return []

    return validate


def non_future_date(
    message: str = "Дата не может быть в будущем.",
) -> Validator[ObjectT, date]:
    def validate(_: ObjectT, value: date | None) -> list[str]:
        if value is None:
            return []
        if value > date.today():
            return [message]
        return []

    return validate


def non_future_datetime(
    now_factory: Callable[[], datetime] | None = None,
    message: str = "Дата/время не может быть в будущем.",
) -> Validator[ObjectT, datetime]:
    now_factory = now_factory or datetime.now

    def validate(_: ObjectT, value: datetime | None) -> list[str]:
        if value is None:
            return []
        if value > now_factory():
            return [message]
        return []

    return validate