from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.sql.elements import ColumnElement


def normalized_name_expr(col) -> ColumnElement[str]:
    """
    SQL expression for normalized name comparison.

    Mirrors normalize_human_name():
    - lower()
    - replace ё -> е

    NOTE:
    - We intentionally do NOT collapse spaces on DB side.
      That is handled on input side.
    """
    return func.replace(func.lower(col), "ё", "е")