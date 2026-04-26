from __future__ import annotations

from core.interaction.input import (
    date_field,
    decimal_field,
    enum_field,
    int_field,
    non_future_date,
    positive_decimal,
    positive_int,
    text,
)
from core.interaction.ui.binding import process
from core.interaction.ui.components.process.patterns.object_input import (
    ConfirmStepCallbacks, InputFlowMode,
)
from core.interaction.ui.components.process.patterns.object_input.simple import (
    SimpleObjectProcess,
)

from pipubot.domains.tutoring.enums.student import (
    Currency,
    ExamTrack,
    SchoolGrade,
    StudyFormat,
    StudyLanguage,
)
from pipubot.domains.tutoring.students.create_service import create_student_service
from pipubot.domains.tutoring.students.errors import CreateStudentError
from pipubot.domains.tutoring.students.mapper import draft_to_create_student_dto
from pipubot.domains.tutoring.students.results import StudentDraft


@process("add_student")
class AddStudentProcess(SimpleObjectProcess[StudentDraft]):
    input_step_name = "ask_student_add_info"
    edit_step_name = "edit_student_info"
    confirm_step_name = "confirm_add_student"

    model = StudentDraft

    flow_mode_value = InputFlowMode.INPUT_CONFIRM

    fields = [
        text("full_name", "ФИО", required=True),
        decimal_field(
            "default_rate",
            "Ставка",
            required=True,
            validator=positive_decimal("Ставка должна быть больше 0."),
        ),
        int_field(
            "default_duration_min",
            "Длительность урока",
            validator=positive_int("Длительность должно быть больше 0."),
        ),
        text("telegram_link", "Telegram"),
        text("email", "Email"),
        text("google_drive_link", "Google Drive"),

        # Если school_grade у Вас реально enum SchoolGrade,
        # лучше заменить aliases на реальные enum members проекта.
        enum_field(
            "school_grade",
            "Класс",
            SchoolGrade,
            aliases={
                # 1–4
                "1": SchoolGrade.GRADE_1,
                "1 класс": SchoolGrade.GRADE_1,
                "2": SchoolGrade.GRADE_2,
                "2 класс": SchoolGrade.GRADE_2,
                "3": SchoolGrade.GRADE_3,
                "3 класс": SchoolGrade.GRADE_3,
                "4": SchoolGrade.GRADE_4,
                "4 класс": SchoolGrade.GRADE_4,

                # 5–8
                "5": SchoolGrade.GRADE_5,
                "5 класс": SchoolGrade.GRADE_5,
                "6": SchoolGrade.GRADE_6,
                "6 класс": SchoolGrade.GRADE_6,
                "7": SchoolGrade.GRADE_7,
                "7 класс": SchoolGrade.GRADE_7,
                "8": SchoolGrade.GRADE_8,
                "8 класс": SchoolGrade.GRADE_8,

                # 9–12
                "9": SchoolGrade.GRADE_9,
                "9 класс": SchoolGrade.GRADE_9,
                "10": SchoolGrade.GRADE_10,
                "10 класс": SchoolGrade.GRADE_10,
                "11": SchoolGrade.GRADE_11,
                "11 класс": SchoolGrade.GRADE_11,
                "12": SchoolGrade.GRADE_12,
                "12 класс": SchoolGrade.GRADE_12,

                # взрослые
                "взрослый": SchoolGrade.ADULT,
                "взрослые": SchoolGrade.ADULT,
                "adult": SchoolGrade.ADULT,

                # поступление
                "поступление": SchoolGrade.ADMISSION,
                "экзамен": SchoolGrade.ADMISSION,
                "вступительные": SchoolGrade.ADMISSION,
                "admission": SchoolGrade.ADMISSION,
            },
        ),

        enum_field(
            "exam_track",
            "Направление экзамена",
            ExamTrack,
            aliases={
                "basic": ExamTrack.BASIC_9,
                "pohi": ExamTrack.BASIC_9,
                "lai": ExamTrack.WIDE,
                "kitsas": ExamTrack.NARROW,
                "широкий": ExamTrack.WIDE,
                "узкий": ExamTrack.NARROW,
            },
        ),
        enum_field(
            "study_language",
            "Язык обучения",
            StudyLanguage,
            aliases={
                "ru": StudyLanguage.RUSSIAN,
                "russian": StudyLanguage.RUSSIAN,
                "русский": StudyLanguage.RUSSIAN,
                "ee": StudyLanguage.ESTONIAN,
                "estonian": StudyLanguage.ESTONIAN,
                "эстонский": StudyLanguage.ESTONIAN,
            },
        ),
        enum_field(
            "study_format",
            "Формат занятий",
            StudyFormat,
            aliases={
                "online": StudyFormat.ONLINE,
                "offline": StudyFormat.OFFLINE,
                "mixed": StudyFormat.MIXED,
                "онлайн": StudyFormat.ONLINE,
                "офлайн": StudyFormat.OFFLINE,
                "смешанный": StudyFormat.MIXED,
            },
        ),
        decimal_field(
            "planned_hours_per_week",
            "План часов в неделю",
            validator=positive_decimal("Ставка должна быть больше 0."),
        ),
        date_field(
            "started_on",
            "Дата начала",
            validator=non_future_date("Дата начала не может быть в будущем."),
        ),
        text("notes", "Заметки"),
        enum_field(
            "default_currency",
            "Валюта",
            Currency,
            aliases={
                "eur": Currency.EUR,
                "euro": Currency.EUR,
                "евро": Currency.EUR,
            },
        ),
    ]

    positional_fields = (
        "full_name",
        "default_rate",
        "default_duration_min",
        "telegram_link",
        "email",
        "google_drive_link",
        "school_grade",
        "exam_track",
    )

    aliases = {
        "имя": "full_name",
        "фио": "full_name",
        "name": "full_name",
        "full name": "full_name",

        "ставка": "default_rate",
        "цена": "default_rate",
        "rate": "default_rate",

        "длительность": "default_duration_min",
        "длительность урока": "default_duration_min",
        "minutes": "default_duration_min",
        "duration": "default_duration_min",

        "telegram": "telegram_link",
        "телеграм": "telegram_link",
        "telegram link": "telegram_link",
        "ссылка на телеграм": "telegram_link",

        "email": "email",
        "почта": "email",

        "google drive": "google_drive_link",
        "google drive link": "google_drive_link",
        "гугл диск": "google_drive_link",
        "ссылка на гугл диск": "google_drive_link",

        "класс": "school_grade",
        "grade": "school_grade",

        "экзамен": "exam_track",
        "направление экзамена": "exam_track",
        "exam track": "exam_track",

        "язык": "study_language",
        "язык обучения": "study_language",
        "study language": "study_language",

        "формат": "study_format",
        "формат занятий": "study_format",
        "study format": "study_format",

        "часы в неделю": "planned_hours_per_week",
        "план часов в неделю": "planned_hours_per_week",
        "hours per week": "planned_hours_per_week",

        "дата начала": "started_on",
        "start date": "started_on",

        "заметки": "notes",
        "notes": "notes",

        "валюта": "default_currency",
        "currency": "default_currency",
    }

    def validate_object(self, user_input, obj: StudentDraft) -> list[str]:
        errors: list[str] = []

        try:
            draft_to_create_student_dto(
                tutor_user_id=user_input.telegram_id,
                draft=obj,
            )
        except ValueError as e:
            errors.append(str(e))

        return errors

    async def submit_object(self, user_input, obj: StudentDraft) -> None:
        dto = draft_to_create_student_dto(
            tutor_user_id=user_input.telegram_id,
            draft=obj,
        )

        student = await create_student_service(
            user_input.session,
            data=dto,
        )

        user_input.state.update_process_payload(
            self._key(),
            created_student_id=student.id,
        )

    def on_submit_error(
            self,
            user_input,
            *,
            obj: StudentDraft,
            error: Exception,
    ) -> list[str]:
        if isinstance(error, CreateStudentError):
            return [str(error)]

        return super().on_submit_error(
            user_input,
            obj=obj,
            error=error,
        )
