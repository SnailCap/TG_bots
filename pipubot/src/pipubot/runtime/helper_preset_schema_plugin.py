from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import text

from core.runtime.context.runtime_context import RuntimeContext


@dataclass(slots=True)
class HelperPresetSchemaPlugin:
    async def start(self, app: Any) -> None:
        runtime = RuntimeContext(app)
        if not runtime.has_engine():
            raise RuntimeError("DB engine is not available for HelperPresetSchemaPlugin.")

        engine = runtime.get_engine()
        if engine.dialect.name != "postgresql":
            return

        async with engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    ALTER TABLE helper_text_presets
                    DROP CONSTRAINT IF EXISTS ck_helper_text_presets_bottom_extra_nonneg
                    """
                )
            )

    async def stop(self) -> None:
        return
