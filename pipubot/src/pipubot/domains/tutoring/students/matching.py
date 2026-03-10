from __future__ import annotations


def normalize_human_name(s: str) -> str:
    """
    Stable normalization for matching human names.

    - Strip
    - collapse spaces
    - case fold
    - ё -> е
    """
    s = " ".join(s.strip().split()).casefold()
    return s.replace("ё", "е")
