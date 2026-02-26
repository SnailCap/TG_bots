from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

def button_ref_to_dict(ref: ButtonRef) -> dict[str, Any]:
    return {
        "key": ref.key,
        "vars": dict(ref.vars),
        "visible": bool(ref.visible),
    }


def button_ref_from_dict(data: Mapping[str, Any]) -> ButtonRef:
    key = str(data.get("key", "")).strip()
    vars_ = data.get("vars") or {}
    visible = data.get("visible", True)
    return ButtonRef(key=key, vars=vars_, visible=bool(visible))

@dataclass(frozen=True, slots=True)
class ButtonRef:
    """
    Reference to a button config by key + optional template vars.

    - key: unique button identifier from configs (group: buttons).
    - vars: vars used to format config templates (text/callback_data/url).
    - visible: allows temporary hiding without removing from layout.
    """
    key: str
    vars: Mapping[str, Any] = field(default_factory=dict)
    visible: bool = True

    def with_vars(self, **kwargs: Any) -> "ButtonRef":
        merged = dict(self.vars)
        merged.update(kwargs)
        return ButtonRef(key=self.key, vars=merged, visible=self.visible)

    def hidden(self) -> "ButtonRef":
        if not self.visible:
            return self
        return ButtonRef(key=self.key, vars=self.vars, visible=False)

    def shown(self) -> "ButtonRef":
        if self.visible:
            return self
        return ButtonRef(key=self.key, vars=self.vars, visible=True)