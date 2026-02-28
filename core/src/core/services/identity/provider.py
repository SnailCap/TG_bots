from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import User
from core.db.repositories.user_repository import (
    create_or_update_user,
    get_user_by_telegram_id,
    set_user_role,
)
from core.interaction.types.user_role import UserRole


@dataclass(slots=True, frozen=True)
class DbIdentityProvider:
    async def ensure_user(
            self,
            session: AsyncSession,
            telegram_id: int,
            username: Optional[str],
            first_name: Optional[str],
            last_name: Optional[str],
    ) -> User:
        return await create_or_update_user(
            session,
            telegram_id=telegram_id,
            telegram_username=username,
            first_name=first_name,
            last_name=last_name,
            role=None,
            stripe_customer_id=None,
        )

    async def get_user(self, session: AsyncSession, telegram_id: int) -> Optional[User]:
        return await get_user_by_telegram_id(session, telegram_id)

    async def ensure_and_get_user(
            self,
            *,
            session: AsyncSession,
            telegram_id: int,
            username: Optional[str],
            first_name: Optional[str],
            last_name: Optional[str],
    ) -> User:
        """
        Удобный метод: сначала пытается получить, если нет — создаёт.
        """
        user = await self.get_user(session, telegram_id)
        if user is not None:
            return user

        return await self.ensure_user(
            session=session,
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )

    async def upsert_basic_profile(
            self,
            *,
            session: AsyncSession,
            telegram_id: int,
            username: Optional[str] = None,
            first_name: Optional[str] = None,
            last_name: Optional[str] = None,
    ) -> User:
        """
        Явный upsert профиля (аналог ensure_user, но с дефолтами).
        """
        return await create_or_update_user(
            session,
            telegram_id=telegram_id,
            telegram_username=username,
            first_name=first_name,
            last_name=last_name,
            role=None,
            stripe_customer_id=None,
        )

    async def set_role(
            self,
            *,
            session: AsyncSession,
            telegram_id: int,
            role: UserRole | str,
    ) -> bool:
        return await set_user_role(session, telegram_id, str(role))
