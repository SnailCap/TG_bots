from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Callable, TypeAlias, TypeVar

from pipubot.domains.tutoring.enums.enums import (
    ExamTrack,
    SchoolGrade,
    StudyFormat,
    StudyLanguage,
)


FieldParser: TypeAlias = Callable[[str], Any]
FieldFormatter: TypeAlias = Callable[[Any], str]
FieldSerializer: TypeAlias = Callable[[Any], Any]
FieldDeserializer: TypeAlias = Callable[[Any], Any]
FieldValidator: TypeAlias = Callable[[Any], str | None]

EnumT = TypeVar("EnumT", bound=Enum)


def parse_text(value: str) -> str:
    return value.strip()


def parse_decimal(value: str) -> Decimal | None:
    normalized = value.strip().replace(",", ".")
    if not normalized:
        return None

    try:
        return Decimal(normalized)
    except InvalidOperation as e:
        raise ValueError("должно быть числом") from e


def parse_int(value: str) -> int | None:
    normalized = value.strip()
    if not normalized:
        return None

    try:
        return int(normalized)
    except ValueError as e:
        raise ValueError("должно быть целым числом") from e


def parse_date_iso(value: str) -> date | None:
    normalized = value.strip()
    if not normalized:
        return None

    try:
        return date.fromisoformat(normalized)
    except ValueError as e:
        raise ValueError("должно быть датой в формате YYYY-MM-DD") from e


def _normalize_enum_lookup_key(value: str) -> str:
    return (
        value.strip()
        .lower()
        .replace(" ", "")
        .replace("-", "")
        .replace("_", "")
    )


def _build_enum_aliases(
    enum_cls: type[EnumT],
    aliases_by_member_name: dict[str, tuple[str, ...]],
) -> dict[str, EnumT]:
    result: dict[str, EnumT] = {}

    for member_name, aliases in aliases_by_member_name.items():
        member = enum_cls.__members__.get(member_name)
        if member is None:
            continue

        for alias in aliases:
            result[_normalize_enum_lookup_key(alias)] = member

    return result


def make_enum_parser(
    enum_cls: type[EnumT],
    *,
    field_label: str,
    aliases: dict[str, EnumT] | None = None,
) -> Callable[[str], EnumT | None]:
    aliases = aliases or {}

    normalized_aliases = {
        _normalize_enum_lookup_key(key): enum_value
        for key, enum_value in aliases.items()
    }

    def parser(value: str) -> EnumT | None:
        normalized = value.strip()
        if not normalized:
            return None

        lookup_key = _normalize_enum_lookup_key(normalized)

        alias_match = normalized_aliases.get(lookup_key)
        if alias_match is not None:
            return alias_match

        for member in enum_cls:
            if _normalize_enum_lookup_key(member.name) == lookup_key:
                return member

            member_value = member.value
            if isinstance(member_value, str):
                if _normalize_enum_lookup_key(member_value) == lookup_key:
                    return member

        allowed_values = ", ".join(
            str(member.value) if isinstance(member.value, str) else member.name
            for member in enum_cls
        )
        raise ValueError(
            f"неизвестное значение. Допустимые значения: {allowed_values}"
        )

    return parser


def format_default(value: Any) -> str:
    return "—" if value is None else str(value)


def format_enum(value: Enum | None) -> str:
    if value is None:
        return "—"

    if isinstance(value.value, str):
        return value.value

    return value.name


def serialize_identity(value: Any) -> Any:
    return value


def deserialize_identity(value: Any) -> Any:
    return value


def serialize_decimal(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def deserialize_decimal(value: str | None) -> Decimal | None:
    return None if value is None else Decimal(value)


def serialize_date(value: date | None) -> str | None:
    return None if value is None else value.isoformat()


def deserialize_date(value: str | None) -> date | None:
    return None if value is None else date.fromisoformat(value)


def make_enum_serializer() -> Callable[[Enum | None], str | None]:
    def serializer(value: Enum | None) -> str | None:
        return None if value is None else value.name

    return serializer


def make_enum_deserializer(
    enum_cls: type[EnumT],
) -> Callable[[str | None], EnumT | None]:
    def deserializer(value: str | None) -> EnumT | None:
        if value is None:
            return None
        return enum_cls[value]

    return deserializer


def validate_positive_decimal(value: Decimal | None) -> str | None:
    if value is not None and value <= 0:
        return "Значение должно быть больше 0."
    return None


def validate_positive_int(value: int | None) -> str | None:
    if value is not None and value <= 0:
        return "Значение должно быть больше 0."
    return None


SCHOOL_GRADE_ALIASES = _build_enum_aliases(
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

EXAM_TRACK_ALIASES = _build_enum_aliases(
    ExamTrack,
    {
        "BASIC_SCHOOL": ("основная школа", "9 класс", "pohikool", "basic"),
        "GYMNASIUM": ("гимназия", "gumnaasium", "gymnasium"),
        "B1": ("b1", "экзамен b1", "b1 eksam"),
        "B2": ("b2", "экзамен b2", "b2 eksam"),
        "STATE_EXAM": ("госэкзамен", "riigieksam", "state exam"),
        "SCHOOL_EXAM": ("школьный экзамен", "koolieksam", "school exam"),
    },
)

STUDY_LANGUAGE_ALIASES = _build_enum_aliases(
    StudyLanguage,
    {
        "ESTONIAN": ("эстонский", "estonian", "eesti"),
        "RUSSIAN": ("русский", "russian", "vene"),
        "ENGLISH": ("английский", "english", "inglise"),
        "GERMAN": ("немецкий", "german", "saksa"),
    },
)

STUDY_FORMAT_ALIASES = _build_enum_aliases(
    StudyFormat,
    {
        "ONLINE": ("онлайн", "online", "zoom", "google meet", "meet"),
        "OFFLINE": ("офлайн", "offline", "очно", "на месте"),
        "HYBRID": ("гибрид", "hybrid", "смешанный"),
        "INDIVIDUAL": ("индивидуально", "индивидуальный", "individual"),
        "GROUP": ("группа", "групповой", "group"),
    },
)


@dataclass(frozen=True, slots=True)
class StudentFieldSpec:
    field_name: str
    label: str
    aliases: tuple[str, ...]
    parser: FieldParser

    required: bool = False
    allow_positional: bool = False
    include_in_confirm: bool = True

    formatter: FieldFormatter = format_default
    serializer: FieldSerializer = serialize_identity
    deserializer: FieldDeserializer = deserialize_identity
    validator: FieldValidator | None = None


STUDENT_FIELD_SPECS: tuple[StudentFieldSpec, ...] = (
    StudentFieldSpec(
        field_name="full_name",
        label="Имя",
        aliases=("имя", "name", "фио", "full_name"),
        parser=parse_text,
        required=True,
        allow_positional=True,
    ),
    StudentFieldSpec(
        field_name="default_rate",
        label="Ставка",
        aliases=("ставка", "rate", "цена", "default_rate"),
        parser=parse_decimal,
        required=True,
        allow_positional=True,
        serializer=serialize_decimal,
        deserializer=deserialize_decimal,
        validator=validate_positive_decimal,
    ),
    StudentFieldSpec(
        field_name="default_duration_min",
        label="Длительность урока (в минутах)",
        aliases=(
            "длительность",
            "длительность урока",
            "длительность урока (в минутах)",
            "duration",
            "minutes",
            "default_duration_min",
        ),
        parser=parse_int,
        allow_positional=True,
        validator=validate_positive_int,
    ),
    StudentFieldSpec(
        field_name="telegram_link",
        label="Telegram ссылка",
        aliases=(
            "телеграм ссылка",
            "ссылка на телеграм",
            "телеграм",
            "telegram",
            "telegram link",
            "telegram_link",
        ),
        parser=parse_text,
        allow_positional=True,
    ),
    StudentFieldSpec(
        field_name="email",
        label="Email",
        aliases=("почта", "email"),
        parser=parse_text,
        allow_positional=True,
    ),
    StudentFieldSpec(
        field_name="google_drive_link",
        label="Google Drive ссылка",
        aliases=(
            "гугл диск",
            "гугл диск ссылка",
            "google drive",
            "google drive link",
            "google_drive_link",
        ),
        parser=parse_text,
        allow_positional=True,
    ),
    StudentFieldSpec(
        field_name="school_grade",
        label="Класс",
        aliases=("класс", "grade", "school_grade"),
        parser=make_enum_parser(
            SchoolGrade,
            field_label="Класс",
            aliases=SCHOOL_GRADE_ALIASES,
        ),
        allow_positional=True,
        formatter=format_enum,
        serializer=make_enum_serializer(),
        deserializer=make_enum_deserializer(SchoolGrade),
    ),
    StudentFieldSpec(
        field_name="exam_track",
        label="Направление экзамена",
        aliases=("направление экзамена", "экзамен", "exam_track"),
        parser=make_enum_parser(
            ExamTrack,
            field_label="Направление экзамена",
            aliases=EXAM_TRACK_ALIASES,
        ),
        allow_positional=True,
        formatter=format_enum,
        serializer=make_enum_serializer(),
        deserializer=make_enum_deserializer(ExamTrack),
    ),
    StudentFieldSpec(
        field_name="study_language",
        label="Язык обучения",
        aliases=("язык обучения", "язык", "study_language"),
        parser=make_enum_parser(
            StudyLanguage,
            field_label="Язык обучения",
            aliases=STUDY_LANGUAGE_ALIASES,
        ),
        formatter=format_enum,
        serializer=make_enum_serializer(),
        deserializer=make_enum_deserializer(StudyLanguage),
    ),
    StudentFieldSpec(
        field_name="study_format",
        label="Формат занятий",
        aliases=("формат занятий", "формат", "study_format"),
        parser=make_enum_parser(
            StudyFormat,
            field_label="Формат занятий",
            aliases=STUDY_FORMAT_ALIASES,
        ),
        formatter=format_enum,
        serializer=make_enum_serializer(),
        deserializer=make_enum_deserializer(StudyFormat),
    ),
    StudentFieldSpec(
        field_name="planned_hours_per_week",
        label="План часов в неделю",
        aliases=(
            "план часов в неделю",
            "часы в неделю",
            "planned_hours_per_week",
        ),
        parser=parse_decimal,
        serializer=serialize_decimal,
        deserializer=deserialize_decimal,
        validator=validate_positive_decimal,
    ),
    StudentFieldSpec(
        field_name="started_on",
        label="Дата начала",
        aliases=("дата начала", "started_on", "start date"),
        parser=parse_date_iso,
        serializer=serialize_date,
        deserializer=deserialize_date,
    ),
    StudentFieldSpec(
        field_name="notes",
        label="Заметки",
        aliases=("заметки", "notes"),
        parser=parse_text,
    ),
)

FIELD_SPEC_BY_NAME: dict[str, StudentFieldSpec] = {
    spec.field_name: spec
    for spec in STUDENT_FIELD_SPECS
}

ALIAS_TO_FIELD_NAME: dict[str, str] = {
    alias.strip().lower(): spec.field_name
    for spec in STUDENT_FIELD_SPECS
    for alias in spec.aliases
}

POSITIONAL_FIELD_ORDER: tuple[str, ...] = tuple(
    spec.field_name
    for spec in STUDENT_FIELD_SPECS
    if spec.allow_positional
)