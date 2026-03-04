from __future__ import annotations

from dataclasses import dataclass
from html import escape as html_escape
from typing import Any, Mapping, Optional

from telegram import InlineKeyboardButton

from core.interaction.config.loader import ConfigLoader


class ButtonBuildError(RuntimeError):
    """Base error for button building."""


class ButtonConfigNotFound(ButtonBuildError):
    pass


class InvalidButtonConfig(ButtonBuildError):
    pass


class ButtonPlaceholderFormatError(ButtonBuildError):
    pass


@dataclass(slots=True)
class ButtonBuilder:
    """
    Строит InlineKeyboardButton по key из группы buttons.

    Ожидаемый конфиг кнопки (JSON):
      {"key": "...", "text": "...", "callback_data": "..."}
      {"key": "...", "text": "...", "link": "..."}  # url

    Важно: ровно одно из callback_data / link.

    Дополнительно:
      - text/callback_data/link могут быть шаблонами с {placeholders}
      - vars подаются из ButtonRef.vars
    """
    loader: ConfigLoader

    def build(
        self,
        key: str,
        *,
        vars: Optional[Mapping[str, Any]] = None,
        html_escape_vars: bool = False,
    ) -> InlineKeyboardButton:
        cfg = self.loader.load_buttons().get(key)
        if cfg is None:
            raise ButtonConfigNotFound(f"Button config not found: '{key}'")
        return self.build_from_config(cfg, key=key, vars=vars, html_escape_vars=html_escape_vars)

    def build_from_config(
        self,
        cfg: Mapping[str, Any],
        *,
        key: str = "<inline>",
        vars: Optional[Mapping[str, Any]] = None,
        html_escape_vars: bool = False,
    ) -> InlineKeyboardButton:
        self._validate_mapping(cfg, key=key)

        raw_text = self._require_non_empty_str(cfg, "text", key=key)
        action_kind, action_value = self._resolve_action(cfg, key=key)

        safe_vars = self._prepare_vars(vars, html_escape_vars=html_escape_vars)

        text = self._format_template(raw_text, safe_vars, key=key, field="text")
        action_value_fmt = self._format_template(action_value, safe_vars, key=key, field=action_kind)

        if action_kind == "callback_data":
            return InlineKeyboardButton(text=text, callback_data=action_value_fmt)

        # action_kind == "link"
        return InlineKeyboardButton(text=text, url=action_value_fmt)

    # -----------------------
    # internals
    # -----------------------
    @staticmethod
    def _validate_mapping(cfg: Any, *, key: str) -> None:
        if not isinstance(cfg, Mapping):
            raise InvalidButtonConfig(f"Button config must be a mapping. key={key}")

    @staticmethod
    def _require_non_empty_str(cfg: Mapping[str, Any], field: str, *, key: str) -> str:
        value = cfg.get(field)
        if not isinstance(value, str) or not value.strip():
            raise InvalidButtonConfig(f"Button '{field}' must be a non-empty string. key={key}")
        return value.strip()

    @staticmethod
    def _resolve_action(cfg: Mapping[str, Any], *, key: str) -> tuple[str, str]:
        """
        Returns:
          ("callback_data", "<value>") or ("link", "<value>")
        """
        callback_data = cfg.get("callback_data")
        link = cfg.get("link")

        has_callback = isinstance(callback_data, str) and callback_data.strip()
        has_link = isinstance(link, str) and link.strip()

        if has_callback == has_link:
            # True/True or False/False => invalid
            raise InvalidButtonConfig(
                f"Button config must contain exactly one of 'callback_data' or 'link'. key={key}"
            )

        if has_callback:
            return "callback_data", str(callback_data).strip()

        return "link", str(link).strip()

    @staticmethod
    def _prepare_vars(
        vars: Optional[Mapping[str, Any]],
        *,
        html_escape_vars: bool,
    ) -> Mapping[str, Any]:
        if not vars:
            return {}

        if not html_escape_vars:
            return vars

        return {k: (html_escape(v) if isinstance(v, str) else v) for k, v in vars.items()}

    @staticmethod
    def _format_template(template: str, vars: Mapping[str, Any], *, key: str, field: str) -> str:
        try:
            # Важно: даже если vars пустые, .format() позволит рано поймать KeyError,
            # если в шаблоне есть {something}. Это лучше, чем отправить кривую кнопку.
            return template.format(**vars)
        except Exception as e:
            raise ButtonPlaceholderFormatError(
                f"Failed to format button template. key={key} field={field} template={template!r} vars={dict(vars)!r}. {e}"
            ) from e