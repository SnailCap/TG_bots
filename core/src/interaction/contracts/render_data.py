from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Union, Dict, Any

@dataclass
class RenderData:
    chat_id: Union[int, str]
    message_id: Optional[int] = None
    text_vars: Dict[str, Any] = field(default_factory=dict)
    kb_vars: Dict[str, Any] = field(default_factory=dict)
    parse_mode: Optional[str] = "HTML"