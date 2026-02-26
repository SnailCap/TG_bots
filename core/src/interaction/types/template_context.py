from dataclasses import dataclass, field
from typing import Any


@dataclass
class TemplateContext:
    text: dict[str, Any] = field(default_factory=dict)
    keyboard: dict[str, Any] = field(default_factory=dict)