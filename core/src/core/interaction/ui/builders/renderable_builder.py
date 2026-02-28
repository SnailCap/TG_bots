from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence


from core.interaction.config.loader import ConfigLoader


class RenderableBuildError(RuntimeError):
    """Base error for renderable template building."""


class InvalidRenderableConfig(RenderableBuildError):
    pass


class TextTemplateNotFound(RenderableBuildError):
    pass


@dataclass(frozen=True, slots=True)
class RenderableDTO:
    text_template: str
    keyboard_layout: Optional[Sequence[Sequence[Any]]]


@dataclass(slots=True)
class RenderableBuilder:
    """
    Ожидаемые поля cfg:
      - "text": str
          * если заканчивается на .txt -> читаем файл из text_root_dir
          * иначе -> inline text
      - "keyboard_layout": list[list[str]] | None
    """
    loader: ConfigLoader

    def __init__(self, loader: ConfigLoader) -> None:
        self.loader = loader

    def build_from_config(
        self,
        cfg: Mapping[str, Any],
        *,
        text_root_dir: Path,
        key: str = "<inline>",
    ) -> RenderableDTO:
        if not isinstance(cfg, Mapping):
            raise InvalidRenderableConfig(f"Renderable config must be a mapping. key={key}")

        text_value = cfg.get("text")
        text_template = self._resolve_text_template(text_value, text_root_dir=text_root_dir, key=key)

        layout = cfg.get("keyboard_layout")
        keyboard_layout = self._resolve_keyboard_layout(layout, key=key)
        return RenderableDTO(text_template=text_template, keyboard_layout=keyboard_layout)

    # ---------- internals ----------
    def _resolve_text_template(self, value: Any, *, text_root_dir: Path, key: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise InvalidRenderableConfig(f"Field 'text' must be a non-empty string. key={key}")

        raw = value.strip()

        if raw.lower().endswith(".txt"):
            path = (text_root_dir / raw).resolve()
            if not path.exists() or not path.is_file():
                raise TextTemplateNotFound(
                    f"Text template file not found for key={key}: {raw} (resolved: {path})"
                )
            try:
                return path.read_text(encoding="utf-8")
            except OSError as e:
                raise RenderableBuildError(f"Failed to read text template file: {path}. {e}") from e

        return raw

    def _resolve_keyboard_layout(self, layout: Any, *, key: str) -> Optional[Sequence[Sequence[Any]]]:
        if layout is None:
            return None
        if not isinstance(layout, Sequence) or isinstance(layout, (str, bytes)):
            raise InvalidRenderableConfig(f"Field 'keyboard_layout' must be a sequence of rows. key={key}")
        return layout