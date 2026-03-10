from __future__ import annotations

from enum import Enum
from typing import TypeVar

from pipubot.domains.tutoring.enums.student import SchoolGrade, ExamTrack, StudyLanguage, StudyFormat

EnumT = TypeVar("EnumT", bound=Enum)


def normalize_enum_lookup_key(value: str) -> str:
    return (
        value.strip()
        .lower()
        .replace(" ", "")
        .replace("-", "")
        .replace("_", "")
    )


def build_enum_aliases(
    enum_cls: type[EnumT],
    aliases_by_member_name: dict[str, tuple[str, ...]],
) -> dict[str, EnumT]:
    result: dict[str, EnumT] = {}

    for member_name, aliases in aliases_by_member_name.items():
        member = enum_cls.__members__.get(member_name)
        if member is None:
            continue

        for alias in aliases:
            result[normalize_enum_lookup_key(alias)] = member

    return result


SCHOOL_GRADE_ALIASES = build_enum_aliases(
    SchoolGrade,
    {
        "GRADE_1": ("1", "1 класс", "1кл"),
        "GRADE_2": ("2", "2 класс", "2кл"),
        "GRADE_3": ("3", "3 класс", "3кл"),
        "GRADE_4": ("4", "4 класс", "4кл"),
        "GRADE_5": ("5", "5 класс", "5кл"),
        "GRADE_6": ("6", "6 класс", "6кл"),
        "GRADE_7": ("7", "7 класс", "7кл"),
        "GRADE_8": ("8", "8 класс", "8кл"),
        "GRADE_9": ("9", "9 класс", "9кл"),
        "GRADE_10": ("10", "10 класс", "10кл"),
        "GRADE_11": ("11", "11 класс", "11кл"),
        "GRADE_12": ("12", "12 класс", "12кл"),
    },
)

EXAM_TRACK_ALIASES = build_enum_aliases(
    ExamTrack,
    {
        "BASIC_SCHOOL": ("основная школа", "9 класс", "pohikool", "basic"),
        "GYMNASIUM": ("гимназия", "gumnaasium", "gymnasium"),
        "STATE_EXAM": ("госэкзамен", "riigieksam", "state exam"),
        "SCHOOL_EXAM": ("школьный экзамен", "koolieksam", "school exam"),
    },
)

STUDY_LANGUAGE_ALIASES = build_enum_aliases(
    StudyLanguage,
    {
        "ESTONIAN": ("эстонский", "estonian", "", "eesti"),
        "RUSSIAN": ("русский", "russian", "vene"),
        "ENGLISH": ("английский", "english", "inglise"),
        "GERMAN": ("немецкий", "german", "saksa"),
    },
)

STUDY_FORMAT_ALIASES = build_enum_aliases(
    StudyFormat,
    {
        "ONLINE": ("онлайн", "online", "zoom", "google meet", "meet"),
        "OFFLINE": ("офлайн", "offline", "очно", "на месте"),
        "HYBRID": ("гибрид", "hybrid", "смешанный"),
        "INDIVIDUAL": ("индивидуально", "индивидуальный", "individual"),
        "GROUP": ("группа", "групповой", "group"),
    },
)