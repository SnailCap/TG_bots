from dataclasses import dataclass

from core.runtime.app_config import AppConfig

@dataclass(frozen=True, slots=True)
class PipubotConfig(AppConfig):
    ...