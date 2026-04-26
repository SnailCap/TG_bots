from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, Sequence

from core.db import Base
from core.runtime.context.runtime_context import RuntimeContext


@dataclass(slots=True)
class EnsureTablesPlugin:
    import_modules: Sequence[str]

    async def start(self, app: Any) -> None:
        for module_name in self.import_modules:
            importlib.import_module(module_name)

        runtime = RuntimeContext(app)
        if not runtime.has_engine():
            raise RuntimeError("DB engine is not available for EnsureTablesPlugin.")

        engine = runtime.get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def stop(self) -> None:
        return
