from __future__ import annotations

from enum import Enum


class StudentState(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    INACTIVE = "INACTIVE"


class SchoolGrade(str, Enum):
    GRADE_1 = "GRADE_1"
    GRADE_2 = "GRADE_2"
    GRADE_3 = "GRADE_3"
    GRADE_4 = "GRADE_4"
    GRADE_5 = "GRADE_5"
    GRADE_6 = "GRADE_6"
    GRADE_7 = "GRADE_7"
    GRADE_8 = "GRADE_8"
    GRADE_9 = "GRADE_9"
    GRADE_10 = "GRADE_10"
    GRADE_11 = "GRADE_11"
    GRADE_12 = "GRADE_12"
    ADULT = "ADULT"
    ADMISSION = "ADMISSION"


class PaymentAccount(str, Enum):
    KONSTANTIN_SWEDBANK = "KONSTANTIN_SWEDBANK"
    KONSTANTIN_REVOLUT = "KONSTANTIN_REVOLUT"
    DIANA_KISS = "DIANA_KISS"
    ALJONA_BUKATY = "ALJONA_BUKATY"


class ExamTrack(str, Enum):
    WIDE = "WIDE"
    NARROW = "NARROW"
    BASIC_9 = "BASIC_9"
    ADMISSION_TEST = "ADMISSION_TEST"


class StudyLanguage(str, Enum):
    RUSSIAN = "RUSSIAN"
    ESTONIAN = "ESTONIAN"
    ENGLISH = "ENGLISH"


class StudyFormat(str, Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    HYBRID = "HYBRID"
