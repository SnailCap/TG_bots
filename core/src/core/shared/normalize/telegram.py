from __future__ import annotations

from html import escape as html_escape

from core.shared.normalize.strings import normalize_required_str


def normalize_telegram_username(value: str | None) -> str | None:
    if value is None:
        return None

    username = value.strip()

    if username.startswith("@"):
        username = username[1:]

    username = username.strip()

    return username or None


def html_link(text: str, url: str) -> str:
    """
    Build an HTML anchor for Telegram messages.

    Use with parse_mode=ParseMode.HTML.
    """
    label = normalize_required_str(text, field_name="text")
    href = normalize_required_str(url, field_name="url")

    return f'<a href="{html_escape(href, quote=True)}">{html_escape(label)}</a>'


def html_link_block(text: str, url: str, *, line_width: int, filler_char: str = "-") -> str:
    """
    Build a two-line clickable block that points both lines to the same URL.

    The first line is padded to at least `line_width` characters.
    The second line is composed only of `filler_char`.
    """
    label = normalize_required_str(text, field_name="text")
    href = normalize_required_str(url, field_name="url")
    if not isinstance(filler_char, str) or filler_char == "":
        raise ValueError("filler_char is required")

    width = max(int(line_width), len(label))
    first_line = label + (filler_char * (width - len(label)))
    second_line = filler_char * width

    return "\n".join(
        (
            html_link(first_line, href),
            html_link(second_line, href),
        )
    )
