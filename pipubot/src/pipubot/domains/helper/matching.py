from __future__ import annotations

import re


_SPACE_RE = re.compile(r"\s+")


def normalize_helper_preset_text(value: str) -> str:
    normalized = _SPACE_RE.sub(" ", value.strip())
    return normalized.casefold()
