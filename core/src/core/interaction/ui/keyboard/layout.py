from __future__ import annotations

from typing import TypeAlias, List

from core.interaction.ui.keyboard.button_ref import ButtonRef

KeyboardRow: TypeAlias = List[ButtonRef]
KeyboardLayout: TypeAlias = List[KeyboardRow]