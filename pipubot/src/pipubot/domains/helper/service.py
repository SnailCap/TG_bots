from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from pipubot.domains.helper.commands import SaveHelperPreset, UpdateHelperPreset
from pipubot.domains.helper.models import HelperTextPreset
from pipubot.domains.helper.repository import (
    delete_helper_preset_by_id,
    get_helper_preset_by_id,
    get_helper_preset_by_text,
    list_helper_presets,
    update_helper_preset_by_id,
    upsert_helper_preset,
)


async def list_helper_presets_service(
    session: AsyncSession,
    *,
    owner_telegram_id: int,
    limit: int = 50,
) -> list[HelperTextPreset]:
    return await list_helper_presets(
        session,
        owner_telegram_id=owner_telegram_id,
        limit=limit,
    )


async def get_helper_preset_by_id_service(
    session: AsyncSession,
    *,
    owner_telegram_id: int,
    preset_id: int,
) -> HelperTextPreset | None:
    return await get_helper_preset_by_id(
        session,
        owner_telegram_id=owner_telegram_id,
        preset_id=preset_id,
    )


async def match_helper_preset_by_text_service(
    session: AsyncSession,
    *,
    owner_telegram_id: int,
    text: str,
) -> HelperTextPreset | None:
    return await get_helper_preset_by_text(
        session,
        owner_telegram_id=owner_telegram_id,
        text=text,
    )


async def save_helper_preset_service(
    session: AsyncSession,
    *,
    data: SaveHelperPreset,
) -> HelperTextPreset:
    text = data.text.strip()
    if not text:
        raise ValueError("Preset text must not be empty.")
    if data.base_length <= 0:
        raise ValueError("Base length must be greater than 0.")

    return await upsert_helper_preset(session, payload=data)


async def update_helper_preset_service(
    session: AsyncSession,
    *,
    data: UpdateHelperPreset,
) -> HelperTextPreset | None:
    text = data.text.strip()
    if not text:
        raise ValueError("Preset text must not be empty.")
    if data.base_length <= 0:
        raise ValueError("Base length must be greater than 0.")

    return await update_helper_preset_by_id(session, payload=data)


async def delete_helper_preset_service(
    session: AsyncSession,
    *,
    owner_telegram_id: int,
    preset_id: int,
) -> bool:
    return await delete_helper_preset_by_id(
        session,
        owner_telegram_id=owner_telegram_id,
        preset_id=preset_id,
    )
