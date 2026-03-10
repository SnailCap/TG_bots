from __future__ import annotations


class LessonMeetLinkError(RuntimeError):
    pass


class LessonNotFoundError(LessonMeetLinkError):
    pass


class LessonGoogleEventBindingError(LessonMeetLinkError):
    pass


class LessonMiroLinkError(RuntimeError):
    pass


class LessonMiroNotFoundError(LessonMiroLinkError):
    pass
