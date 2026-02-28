from __future__ import annotations

from typing import Protocol, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import User


class IdentityProvider(Protocol):
    async def ensure_user(
            self,
            *,
            session: AsyncSession,
            telegram_id: int,
            username: Optional[str],
            first_name: Optional[str],
            last_name: Optional[str],
    ) -> User:
        ...
