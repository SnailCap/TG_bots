from __future__ import annotations


# -------------------------
# Structure validation
# -------------------------
class ConfigStructureError(RuntimeError):
    """Базовая ошибка структуры config-root."""


class ConfigRootNotFound(ConfigStructureError):
    """Корневой путь конфига не существует."""


class RequiredConfigDirMissing(ConfigStructureError):
    """Отсутствуют обязательные директории конфига или они не директории."""


# -------------------------
# Loading / parsing
# -------------------------
class ConfigLoadError(RuntimeError):
    """Базовая ошибка загрузки конфигов."""


class ConfigJsonParseError(ConfigLoadError):
    """JSON не парсится."""


class ConfigNotAJsonObjectError(ConfigLoadError):
    """Top-level JSON не является объектом (dict)."""


class ConfigDuplicateKeyError(ConfigLoadError):
    """Ключ повторяется внутри одной группы."""
