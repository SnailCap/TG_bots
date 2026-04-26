from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from pipubot.domains.helper.commands import SaveHelperPreset, UpdateHelperPreset
from pipubot.domains.helper.matching import normalize_helper_preset_text
from pipubot.domains.helper.models import HelperTextPreset


def _base_stmt(*, owner_telegram_id: int) -> Select[tuple[HelperTextPreset]]:
    return select(HelperTextPreset).where(HelperTextPreset.owner_telegram_id == owner_telegram_id)


async def list_helper_presets(
    session: AsyncSession,
    *,
    owner_telegram_id: int,
    limit: int = 50,
) -> list[HelperTextPreset]:
    stmt = (
        _base_stmt(owner_telegram_id=owner_telegram_id)
        .order_by(HelperTextPreset.updated_at.desc(), HelperTextPreset.id.desc())
        .limit(limit)
    )
    res = await session.scalars(stmt)
    return list(res)


async def get_helper_preset_by_id(
    session: AsyncSession,
    *,
    owner_telegram_id: int,
    preset_id: int,
) -> HelperTextPreset | None:
    stmt = (
        _base_stmt(owner_telegram_id=owner_telegram_id)
        .where(HelperTextPreset.id == preset_id)
        .limit(1)
    )
    return await session.scalar(stmt)


async def get_helper_preset_by_text(
    session: AsyncSession,
    *,
    owner_telegram_id: int,
    text: str,
) -> HelperTextPreset | None:
    normalized_text = normalize_helper_preset_text(text)
    if not normalized_text:
        return None

    stmt = (
        _base_stmt(owner_telegram_id=owner_telegram_id)
        .where(HelperTextPreset.normalized_text == normalized_text)
        .limit(1)
    )
    return await session.scalar(stmt)


async def upsert_helper_preset(
    session: AsyncSession,
    *,
    payload: SaveHelperPreset,
) -> HelperTextPreset:
    normalized_text = normalize_helper_preset_text(payload.text)
    existing = await get_helper_preset_by_text(
        session,
        owner_telegram_id=payload.owner_telegram_id,
        text=payload.text,
    )
    if existing is None:
        existing = HelperTextPreset(
            owner_telegram_id=payload.owner_telegram_id,
            text=payload.text.strip(),
            normalized_text=normalized_text,
            base_length=payload.base_length,
            bottom_extra_symbols=payload.bottom_extra_symbols,
        )
        session.add(existing)
        await session.flush()
        return existing

    existing.text = payload.text.strip()
    existing.normalized_text = normalized_text
    existing.base_length = payload.base_length
    existing.bottom_extra_symbols = payload.bottom_extra_symbols
    await session.flush()
    return existing


async def update_helper_preset_by_id(
    session: AsyncSession,
    *,
    payload: UpdateHelperPreset,
) -> HelperTextPreset | None:
    target = await get_helper_preset_by_id(
        session,
        owner_telegram_id=payload.owner_telegram_id,
        preset_id=payload.preset_id,
    )
    if target is None:
        return None

    normalized_text = normalize_helper_preset_text(payload.text)
    conflict = await get_helper_preset_by_text(
        session,
        owner_telegram_id=payload.owner_telegram_id,
        text=payload.text,
    )
    if conflict is not None and conflict.id != target.id:
        raise ValueError("Preset with this text already exists.")

    target.text = payload.text.strip()
    target.normalized_text = normalized_text
    target.base_length = payload.base_length
    target.bottom_extra_symbols = payload.bottom_extra_symbols
    await session.flush()
    return target


async def delete_helper_preset_by_id(
    session: AsyncSession,
    *,
    owner_telegram_id: int,
    preset_id: int,
) -> bool:
    target = await get_helper_preset_by_id(
        session,
        owner_telegram_id=owner_telegram_id,
        preset_id=preset_id,
    )
    if target is None:
        return False

    await session.delete(target)
    await session.flush()
    return True
