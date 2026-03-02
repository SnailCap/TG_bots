from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from pipubot.domains.tutoring.models.student import TutoringStudent
from pipubot.domains.tutoring.repositories.student_repository import (
    list_students_by_first_name_ci,
    list_students_by_full_name_ci,
)
from pipubot.domains.tutoring.utils.name_normalize import normalize_human_name

ResolveKind = Literal["matched", "unmatched", "ambiguous"]


@dataclass(frozen=True, slots=True)
class StudentResolveResult:
    """
    Safe resolution result (no guessing when ambiguous).

    - matched: student_id is set
    - unmatched: no candidates found (parsed_name may be set)
    - ambiguous: multiple plausible candidates (candidate_ids set), do not auto-pick
    """
    kind: ResolveKind
    parsed_name: str | None
    student_id: int | None = None
    candidate_ids: tuple[int, ...] = ()


# Split only on separators with spaces around them.
# This avoids breaking names like "Anna-Maria".
_SEPARATORS: tuple[str, ...] = (" — ", " – ", " | ", " - ")


def parse_student_name_from_title(title: str | None) -> str | None:
    """
    Extracts a student name from an event title.

    Supported formats:
    - "Имя"
    - "Имя Фамилия"
    - "Имя Фамилия — ..." (tail ignored)
    - "Имя | ..." (tail ignored)

    Returns:
        Name with collapsed spaces, or None.
    """
    if not title:
        return None

    s = title.strip()
    if not s:
        return None

    for sep in _SEPARATORS:
        if sep in s:
            s = s.split(sep, 1)[0].strip()
            break

    s = " ".join(s.split())
    return s or None


def _pick_best_candidate(candidates: list[TutoringStudent]) -> StudentResolveResult:
    """
    Safe picking rules:

    1) If exactly one active candidate -> pick it
    2) Else if exactly one candidate total -> pick it
    3) Else -> ambiguous (do not guess)
    """
    if not candidates:
        return StudentResolveResult(kind="unmatched", parsed_name=None)

    active = [c for c in candidates if c.is_active]
    if len(active) == 1:
        return StudentResolveResult(
            kind="matched",
            parsed_name=None,
            student_id=active[0].id,
            candidate_ids=tuple(c.id for c in candidates),
        )

    if len(candidates) == 1:
        return StudentResolveResult(
            kind="matched",
            parsed_name=None,
            student_id=candidates[0].id,
            candidate_ids=(candidates[0].id,),
        )

    return StudentResolveResult(
        kind="ambiguous",
        parsed_name=None,
        student_id=None,
        candidate_ids=tuple(c.id for c in candidates),
    )


async def resolve_student_id_by_event_title(
    session: AsyncSession,
    *,
    tutor_user_id: int,
    title: str | None,
) -> StudentResolveResult:
    """
    Resolve a student using ONLY the event title ("Имя" or "Имя Фамилия").

    - Never creates students.
    - Never guesses when ambiguous.
    - Prefers exactly one active student when multiple candidates exist.

    Returns:
        StudentResolveResult (matched/unmatched/ambiguous).
    """
    parsed = parse_student_name_from_title(title)
    if not parsed:
        return StudentResolveResult(kind="unmatched", parsed_name=None)

    tokens = parsed.split()
    norm = normalize_human_name(parsed)

    # "Имя Фамилия" (or more tokens) -> exact full_name match only
    if len(tokens) >= 2:
        candidates = await list_students_by_full_name_ci(
            session,
            tutor_user_id=tutor_user_id,
            full_name=norm,
        )
        if not candidates:
            return StudentResolveResult(kind="unmatched", parsed_name=parsed)

        picked = _pick_best_candidate(candidates)
        return StudentResolveResult(
            kind=picked.kind,
            parsed_name=parsed,
            student_id=picked.student_id,
            candidate_ids=picked.candidate_ids,
        )

    # "Имя" only -> match against:
    # - full_name == first_name
    # - full_name startswith "first_name"
    candidates = await list_students_by_first_name_ci(
        session,
        tutor_user_id=tutor_user_id,
        first_name=norm,
    )
    if not candidates:
        return StudentResolveResult(kind="unmatched", parsed_name=parsed)

    picked = _pick_best_candidate(candidates)
    return StudentResolveResult(
        kind=picked.kind,
        parsed_name=parsed,
        student_id=picked.student_id,
        candidate_ids=picked.candidate_ids,
    )