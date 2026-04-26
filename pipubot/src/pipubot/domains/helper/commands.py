from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SaveHelperPreset:
    owner_telegram_id: int
    text: str
    base_length: int
    bottom_extra_symbols: int


@dataclass(frozen=True, slots=True)
class UpdateHelperPreset:
    owner_telegram_id: int
    preset_id: int
    text: str
    base_length: int
    bottom_extra_symbols: int
