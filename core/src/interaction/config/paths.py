from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ResourcePaths:
    """
    Единственный источник правды о путях до конфигов.

    Важно:
    - Внутренняя структура папок (вложенные подпапки/файлы) не ограничивается.
    - Здесь мы фиксируем только якорные директории, которые обязаны существовать.
    """
    root: Path

    @classmethod
    def from_root(cls, root: str | Path) -> "ResourcePaths":
        return cls(root=Path(root))

    def normalized(self) -> "ResourcePaths":
        """Возвращает нормализованный root (resolve без проверки существования)."""
        return ResourcePaths(root=self.root.expanduser().resolve(strict=False))

    # --- anchor dirs ---
    @property
    def buttons_dir(self) -> Path:
        return self.root / "buttons"

    @property
    def notifications_dir(self) -> Path:
        return self.root / "notifications"

    @property
    def pages_dir(self) -> Path:
        return self.root / "pages"

    @property
    def steps_dir(self) -> Path:
        return self.root / "steps"

    # --- text dirs ---
    @property
    def text_dir(self) -> Path:
        """
        Корень для текстовых шаблонов (*.txt), которые подключаются через поле `text`
        (когда значение заканчивается на .txt).
        """
        return self.root / "text"

    @property
    def pages_text_dir(self) -> Path:
        return self.text_dir / "pages"

    @property
    def steps_text_dir(self) -> Path:
        return self.text_dir / "steps"

    @property
    def notifications_text_dir(self) -> Path:
        return self.text_dir / "notifications"

    # --- convenience ---
    def anchor_dirs(self) -> dict[str, Path]:
        """
        Имена якорных папок -> Path.
        Удобно для валидатора структуры и для универсального лоадера.
        """
        return {
            "buttons": self.buttons_dir,
            "notifications": self.notifications_dir,
            "pages": self.pages_dir,
            "steps": self.steps_dir,
        }

    def text_dirs(self) -> dict[str, Path]:
        """
        Текстовые директории по сущностям.
        Можно использовать в валидаторе структуры и в renderable_builder.
        """
        return {
            "pages": self.pages_text_dir,
            "steps": self.steps_text_dir,
            "notifications": self.notifications_text_dir,
        }
