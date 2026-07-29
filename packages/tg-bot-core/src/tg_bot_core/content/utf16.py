from __future__ import annotations


def utf16_length(value: str) -> int:
    """Return Telegram's offset unit count (UTF-16 code units)."""

    return len(value.encode("utf-16-le")) // 2


def utf16_offsets(value: str) -> tuple[int, ...]:
    """Return the UTF-16 offset for every Python string boundary."""

    result = [0]
    current = 0
    for character in value:
        current += utf16_length(character)
        result.append(current)
    return tuple(result)


def index_from_utf16_offset(value: str, offset: int) -> int:
    if offset < 0:
        raise ValueError("UTF-16 offset cannot be negative.")
    for index, candidate in enumerate(utf16_offsets(value)):
        if candidate == offset:
            return index
        if candidate > offset:
            break
    raise ValueError("UTF-16 offset does not fall on a Unicode boundary.")


def utf16_slice(value: str, offset: int, length: int) -> str:
    if length < 0:
        raise ValueError("UTF-16 length cannot be negative.")
    start = index_from_utf16_offset(value, offset)
    end = index_from_utf16_offset(value, offset + length)
    return value[start:end]
