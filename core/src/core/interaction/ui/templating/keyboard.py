from __future__ import annotations

import html
from typing import Any, Dict, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from core.interaction.exceptions.template_errors import PlaceholderFormatError


def _format_field(
    template: Optional[str],
    variables: Dict[str, Any],
    *,
    html_escape_variables: bool,
) -> Optional[str]:
    if template is None:
        return None

    safe_vars = variables
    if html_escape_variables:
        safe_vars = {k: html.escape(str(v)) for k, v in variables.items()}

    try:
        return template.format(**safe_vars)
    except Exception as e:
        raise PlaceholderFormatError(template, variables, e)


def format_inline_keyboard(
    keyboard: InlineKeyboardMarkup,
    variables: Dict[str, Any],
    *,
    html_escape_variables: bool = False,
) -> Optional[InlineKeyboardMarkup]:
    """
    Formats InlineKeyboardMarkup as a template:
      - button.text
      - button.callback_data
      - button.url
      - button.switch_inline_query / switch_inline_query_current_chat
      - button.web_app (url inside web_app) is not handled here unless you add it explicitly

    Keeps structure unchanged.
    """
    if keyboard is None:
        return None
    new_rows = []

    for row in keyboard.inline_keyboard:
        new_row = []
        for button in row:
            new_button = InlineKeyboardButton(
                text=_format_field(button.text, variables, html_escape_variables=html_escape_variables) or "",
                callback_data=_format_field(button.callback_data, variables, html_escape_variables=html_escape_variables),
                url=_format_field(button.url, variables, html_escape_variables=html_escape_variables),
                switch_inline_query=_format_field(
                    button.switch_inline_query, variables, html_escape_variables=html_escape_variables
                ),
                switch_inline_query_current_chat=_format_field(
                    button.switch_inline_query_current_chat, variables, html_escape_variables=html_escape_variables
                ),
            )
            new_row.append(new_button)

        new_rows.append(new_row)

    return InlineKeyboardMarkup(new_rows)
