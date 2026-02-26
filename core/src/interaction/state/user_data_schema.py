from __future__ import annotations

from typing import TypedDict

from typing import Any, cast

from core.src.interaction.utils.normalize_key import normalize_key


class ProcessMeta(TypedDict):
    step_index: int


class ProcessSlot(TypedDict):
    meta: ProcessMeta
    payload: dict[str, Any]


class ProcessesRoot(TypedDict):
    # ключ процесса -> слот процесса
    # (в TypedDict нельзя напрямую "dict[str, ...]" как поле со свободными ключами,
    # поэтому используем alias ниже, а здесь оставим как базовый тип)
    pass


# Для удобства: root dict для процессов
ProcessesDict = dict[str, ProcessSlot]


class UserData(TypedDict, total=False):
    # page state
    current_page: str
    page_history: list[str]
    name: str

    # process state
    current_process: str
    process: ProcessesDict

    # (в будущем можно расширять сюда же другие системные разделы)


def ensure_process_slot(slot: Any) -> ProcessSlot:
    """
    Приводит slot к форме:
    {"meta": {"step_index": int}, "payload": dict}
    """
    if not isinstance(slot, dict):
        slot = {}

    meta = slot.get("meta")
    if not isinstance(meta, dict):
        meta = {}
        slot["meta"] = meta

    step_index = meta.get("step_index", 0)
    try:
        meta["step_index"] = int(step_index)
    except (TypeError, ValueError):
        meta["step_index"] = 0

    payload = slot.get("payload")
    if not isinstance(payload, dict):
        payload = {}
        slot["payload"] = payload

    return cast(ProcessSlot, cast(object, slot))


def ensure_processes_root(value: Any) -> ProcessesDict:
    """
    Приводит корень процессов к dict[str, ProcessSlot],
    выкидывая мусорные значения аккуратно.
    """
    if not isinstance(value, dict):
        return {}

    out: ProcessesDict = {}
    for k, v in value.items():
        if k is None:
            continue
        out[str(k)] = ensure_process_slot(v)
    return out


def ensure_page_history(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(x) for x in value if x is not None]


def ensure_user_data_shape(raw: Any) -> UserData:
    """
    Приводит произвольный store.dump() к UserData (по форме),
    ничего не "ломая": неизвестные поля сохраняются в raw,
    но системные поля нормализуются.
    """
    if not isinstance(raw, dict):
        raw = {}

    ud = cast(UserData, cast(object, raw))

    # normalize page history
    if "page_history" in raw:
        ud["page_history"] = ensure_page_history(raw.get("page_history"))
    else:
        # можно не создавать по умолчанию — но так удобнее
        ud["page_history"] = []

    # normalize processes root
    ud["process"] = ensure_processes_root(raw.get("process", {}))

    # normalize simple string fields if present
    if raw.get("current_page") is not None:
        ud["current_page"] = normalize_key(raw["current_page"])

    if raw.get("current_process") is not None:
        ud["current_process"] = normalize_key(raw["current_process"])

    if raw.get("name") is not None:
        ud["name"] = normalize_key(raw["name"])

    return ud
