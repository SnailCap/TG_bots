from __future__ import annotations


class TutoringError(RuntimeError):
    """Base error for tutoring domain."""
    pass


class EntityNotFoundError(TutoringError):
    pass


class LessonNotFoundError(EntityNotFoundError):
    pass


class StudentNotFoundError(EntityNotFoundError):
    pass


class PaymentNotFoundError(EntityNotFoundError):
    pass


class ConflictError(TutoringError):
    pass


class LessonAlreadyConfirmedError(ConflictError):
    pass


class ValidationError(TutoringError, ValueError):
    pass


class InvalidConfirmPayloadError(ValidationError):
    pass


class TimeRangeError(ValidationError):
    pass