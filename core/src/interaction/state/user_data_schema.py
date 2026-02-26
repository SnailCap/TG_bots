from __future__ import annotations

from typing import Any, Optional, Final, Literal, TypedDict, cast

from core.src.interaction.utils.normalize_key import normalize_key


# --- literals for TypedDict keys (single source of truth) ---
PROC_META: Final[Literal["meta"]] = "meta"
PROC_PAYLOAD: Final[Literal["payload"]] = "payload"

META_STEP_INDEX: Final[Literal["step_index"]] = "step_index"
META_STEP_KEY: Final[Literal["step_key"]] = "step_key"


class ProcessMeta(TypedDict, total=False):
    step_index: int
    step_key: Optional[str]


class ProcessSlot(TypedDict):
    meta: ProcessMeta
    payload: dict[str, Any]


ProcessesDict = dict[str, ProcessSlot]


class UserData(TypedDict, total=False):
    # pages
    current_page: str
    page_history: list[str]
    name: str

    # processes (canonical)
    processes: ProcessesDict
    current_process: str

    # legacy (read-only for migration)
    process: ProcessesDict


# -----------------------
# Factories / Normalizers
# -----------------------

def make_default_process_slot() -> ProcessSlot:
    # centralized shape; if the schema changes - update here only
    return {"meta": {META_STEP_INDEX: 0, META_STEP_KEY: None}, "payload": {}}


def ensure_process_slot(slot: Any) -> ProcessSlot:
    if not isinstance(slot, dict):
        slot = {}

    meta = slot.get(PROC_META)
    if not isinstance(meta, dict):
        meta = {}
        slot[PROC_META] = meta

    # step_index
    step_index = meta.get(META_STEP_INDEX, 0)
    try:
        meta[META_STEP_INDEX] = int(step_index)
    except (TypeError, ValueError):
        meta[META_STEP_INDEX] = 0

    # step_key
    step_key = meta.get(META_STEP_KEY)
    if step_key is None or step_key == "":
        meta[META_STEP_KEY] = None
    else:
        # NOTE: if you don't want normalization here, replace with: str(step_key)
        meta[META_STEP_KEY] = normalize_key(step_key)

    payload = slot.get(PROC_PAYLOAD)
    if not isinstance(payload, dict):
        payload = {}
        slot[PROC_PAYLOAD] = payload

    return cast(ProcessSlot, cast(object, slot))


def ensure_processes_root(value: Any) -> ProcessesDict:
    """
    Normalize processes root into dict[str, ProcessSlot].
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
    Normalize arbitrary store.dump() into a UserData shape.

    Migration:
    - canonical: "processes"
    - legacy: "process"
    We read both, but normalize into "processes".
    """
    if not isinstance(raw, dict):
        raw = {}

    ud = cast(UserData, cast(object, raw))

    # page_history always present and well-formed
    ud["page_history"] = ensure_page_history(raw.get("page_history", []))

    # processes: prefer canonical, fallback to legacy
    processes_raw = raw.get("processes")
    if processes_raw is None:
        processes_raw = raw.get("process", {})

    ud["processes"] = ensure_processes_root(processes_raw)

    # normalize optional scalar fields
    if raw.get("current_page") is not None:
        ud["current_page"] = normalize_key(raw["current_page"])

    if raw.get("current_process") is not None:
        ud["current_process"] = normalize_key(raw["current_process"])

    if raw.get("name") is not None:
        ud["name"] = normalize_key(raw["name"])

    return ud


# ----------------
# Typed slot helpers
# ----------------

def get_step_index(slot: ProcessSlot, default: int = 0) -> int:
    value = slot[PROC_META].get(META_STEP_INDEX, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def set_step_index(slot: ProcessSlot, index: int) -> None:
    slot[PROC_META][META_STEP_INDEX] = int(index)


def get_step_key(slot: ProcessSlot) -> Optional[str]:
    value = slot[PROC_META].get(META_STEP_KEY)
    return normalize_key(value) if value is not None else None


def set_step_key(slot: ProcessSlot, step_key: str | None) -> None:
    slot[PROC_META][META_STEP_KEY] = normalize_key(step_key) if step_key else None


def get_payload(slot: ProcessSlot) -> dict[str, Any]:
    return slot[PROC_PAYLOAD]