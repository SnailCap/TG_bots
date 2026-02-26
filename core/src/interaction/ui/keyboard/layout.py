from __future__ import annotations

from typing import TypeAlias, Sequence, List

from core.src.interaction.ui.keyboard.button_ref import ButtonRef

KeyboardRow: TypeAlias = List[ButtonRef]
KeyboardLayout: TypeAlias = List[KeyboardRow]