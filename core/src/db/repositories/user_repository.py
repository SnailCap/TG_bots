from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.src.db.models import User
from core.src.interaction.types.user_role import UserRole


from sqlalchemy.exc import ProgrammingError
from psycopg.errors import UndefinedTable


async def get_user_by_telegram_id(session, telegram_id: int):
    try:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    except ProgrammingError as e:
        # unwrap original psycopg error
        if isinstance(e.orig, UndefinedTable):
            raise RuntimeError(
                "Database table 'users' does not exist. "
                "Run migrations or create tables manually."
            ) from e
        raise

def _role_to_db(role: Optional[UserRole | str]) -> Optional[str]:
    if role is None:
        return None
    if isinstance(role, UserRole):
        return role.value              # enum -> "admin"
    return str(role).strip().lower()   # строка -> нормализованная строка

def _role_from_db(role_str: str | None) -> Optional[UserRole]:
    if role_str is None:
        return None
    try:
        return UserRole(role_str)      # "admin" -> UserRole.ADMIN
    except ValueError:
        return None

async def create_or_update_user(
    session: AsyncSession,
    *,
    telegram_id: int,
    telegram_username: str = None,
    first_name: Optional[str],
    last_name: Optional[str],
    role: UserRole | str | None = None,        # <-- ПРИНИМАЕМ enum ИЛИ строку
    stripe_customer_id: Optional[str] = None,
) -> User:
    user = await get_user_by_telegram_id(session, telegram_id)
    db_role = _role_to_db(role)

    if user is None:
        user = User(
            telegram_id=telegram_id,
            telegram_username=telegram_username,
            first_name=first_name,
            last_name=last_name,
            role=db_role or UserRole.PUBLIC,
        )
        session.add(user)
        return user

    if first_name is not None:
        user.first_name = first_name
    if last_name is not None:
        user.last_name = last_name
    if db_role is not None:
        user.role = db_role
    if stripe_customer_id is not None:
        user.stripe_customer_id = stripe_customer_id
    if telegram_username is not None:
        user.telegram_username = telegram_username

    return user


async def set_user_role(session: AsyncSession, telegram_id: int, role: str) -> bool:
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        return False
    user.role = role
    return True


async def set_user_stripe_customer_id(
    session: AsyncSession,
    *,
    telegram_id: int,
    stripe_customer_id: str
) -> None:
    """
    Привязывает Stripe customer_id к пользователю по telegram_id.
    Если у пользователя уже есть другой customer_id — заменяет.
    """
    await session.execute(
        update(User)
        .where(User.telegram_id == telegram_id)
        .values(stripe_customer_id=stripe_customer_id)
    )