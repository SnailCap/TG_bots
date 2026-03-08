from __future__ import annotations


class CalendarClientError(RuntimeError):
    pass


class CalendarAuthError(CalendarClientError):
    """401/403 typically."""
    pass


class CalendarSyncTokenExpired(CalendarClientError):
    """
    Google returns 410 Gone when syncToken is invalid/expired.
    Sync service should catch it and fall back to window sync.
    """
    pass


class CalendarRateLimitError(CalendarClientError):
    """429 or quota-limit style responses."""
    pass


class CalendarEventNotFoundError(CalendarClientError):
    """Raised when a Google Calendar event does not exist."""
    pass