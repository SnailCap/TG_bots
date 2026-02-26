from enum import Enum
from typing import Any


def unwrap_enum(obj: Any) -> Any:
    return obj.value if isinstance(obj, Enum) else obj
