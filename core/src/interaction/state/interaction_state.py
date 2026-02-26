from __future__ import annotations

from typing import Any, Optional

from core.src.interaction.contracts.state_store import StateStore
from core.src.interaction.state.user_data_schema import (
    ensure_process_slot,
    ensure_processes_root,
    ensure_page_history,
    ensure_user_data_shape, ProcessesDict, ProcessSlot,
)
from core.src.interaction.types.user_data_key import UserDataPageKey, UserDataProcessKey
from core.src.interaction.utils.normalize_key import normalize_key


class InteractionState:
    """
    Facade over persistent StateStore + per-update ephemeral metadata.

    - Persistent: stored in StateStore (typically PTB user_data).
    - Ephemeral: stored in self._meta and should live for a single update.
    """

    # ---- internal constants to avoid magic strings ----
    _PROC_META: str = "meta"
    _PROC_PAYLOAD: str = "payload"
    _PROC_STEP_INDEX: str = "step_index"

    def __init__(self, store: StateStore) -> None:
        self._store = store
        self._meta: dict[str, Any] = {}  # ephemeral per-update metadata

        # One-time normalize the store shape (idempotent).
        fixed = ensure_user_data_shape(self._store.dump())

        # Apply only the canonical system keys (don't overwrite unknown user keys).
        self._store.set(UserDataPageKey.PAGE_HISTORY, fixed.get("page_history", []))
        self._store.set(UserDataProcessKey.PROCESSES, fixed.get("process", {}))

        if fixed.get("current_page") is not None:
            self._store.set(UserDataPageKey.CURRENT_PAGE, normalize_key(fixed["current_page"]))

        if fixed.get("current_process") is not None:
            self._store.set(UserDataProcessKey.CURRENT_PROCESS, fixed["current_process"])

        if fixed.get("name") is not None:
            self._store.set(UserDataPageKey.NAME, fixed["name"])

    # ====== metadata (ephemeral) ======

    def set_meta(self, key: Any, value: Any) -> None:
        self._meta[normalize_key(key)] = value

    def get_meta(self, key: Any, default: Any = None) -> Any:
        return self._meta.get(normalize_key(key), default)

    def pop_meta(self, key: Any, default: Any = None) -> Any:
        return self._meta.pop(normalize_key(key), default)

    # ====== low-level store passthrough ======

    def set(self, key: Any, value: Any) -> None:
        self._store.set(key, value)

    def get(self, key: Any, default: Any = None) -> Any:
        return self._store.get(key, default)

    def pop(self, key: Any, default: Any = None) -> Any:
        return self._store.pop(key, default)

    def has(self, key: Any) -> bool:
        return self._store.has(key)

    def dump(self) -> dict:
        return self._store.dump()

    # ====== process state (persistent) ======

    def _get_processes_root(self) -> ProcessesDict:
        raw = self.get(UserDataProcessKey.PROCESSES)
        procs = ensure_processes_root(raw)
        self.set(UserDataProcessKey.PROCESSES, procs)
        return procs

    def _get_or_create_process_slot(self, process_name: str) -> ProcessSlot:
        procs = self._get_processes_root()

        slot = procs.get(process_name)
        if slot is None:
            slot = {"meta": {"step_index": 0}, "payload": {}}

        slot = ensure_process_slot(slot)
        procs[process_name] = slot
        self.set(UserDataProcessKey.PROCESSES, procs)
        return slot

    def set_active_process(self, name: str) -> None:
        self.set(UserDataProcessKey.CURRENT_PROCESS, name)
        self._get_or_create_process_slot(str(name))

    def clear_active_process(self) -> None:
        self.pop(UserDataProcessKey.CURRENT_PROCESS)

    def has_active_process(self) -> bool:
        return self.has(UserDataProcessKey.CURRENT_PROCESS)

    def get_active_process(self) -> str:
        name = self.get(UserDataProcessKey.CURRENT_PROCESS)
        if not name:
            raise RuntimeError("No active process is set")

        name_str = str(name)
        # Ensure the slot exists & is well-formed.
        self._get_or_create_process_slot(name_str)
        return name_str

    def get_process_payload(self, process_name: str) -> dict[str, Any]:
        return self._get_or_create_process_slot(process_name)["payload"]

    def update_process_payload(self, process_name: str, **kwargs: Any) -> None:
        slot = self._get_or_create_process_slot(process_name)
        slot["payload"].update(kwargs)

        procs = self._get_processes_root()
        procs[process_name] = slot
        self.set(UserDataProcessKey.PROCESSES, procs)

    def get_step_index(self, process_name: str, default: int = 0) -> int:
        slot = self._get_or_create_process_slot(process_name)
        value = slot["meta"].get("step_index", default)
        try:
            return int(value)
        except (TypeError, ValueError):
            return int(default)

    def set_step_index(self, process_name: str, index: int) -> None:
        slot = self._get_or_create_process_slot(process_name)
        slot["meta"]["step_index"] = int(index)

        procs = self._get_processes_root()
        procs[process_name] = slot
        self.set(UserDataProcessKey.PROCESSES, procs)

    def clear_process_state(self, process_name: str) -> None:
        procs = self._get_processes_root()
        if process_name in procs:
            procs.pop(process_name, None)
            self.set(UserDataProcessKey.PROCESSES, procs)

    # ====== step flow flags (ephemeral) ======
    # (Оставлено для обратной совместимости; в Variant A почти не используется)

    def request_next_step(self) -> None:
        self.set_meta(UserDataProcessKey.NEXT_STEP_REQUESTED, True)

    def consume_next_step_request(self) -> bool:
        return bool(self.pop_meta(UserDataProcessKey.NEXT_STEP_REQUESTED, False))

    def set_finished_process(self, process_name: str) -> None:
        self.set_meta(UserDataProcessKey.FINISHED_PROCESS, process_name)

    def set_canceled_process(self, process_name: str) -> None:
        self.set_meta(UserDataProcessKey.CANCELED_PROCESS, process_name)

    def get_finished_process(self) -> Optional[str]:
        value = self.get_meta(UserDataProcessKey.FINISHED_PROCESS)
        return str(value) if value is not None else None

    def cancel_current_process(self) -> None:
        if not self.has_active_process():
            return

        name = self.get_active_process()
        self.clear_process_state(name)
        self.set_canceled_process(name)
        self.clear_active_process()

        # Clean ephemeral flags that could affect coordinator logic
        self.pop_meta(UserDataProcessKey.NEXT_STEP_REQUESTED, False)
        self.pop_meta(UserDataProcessKey.FINISHED_PROCESS, None)

    # ====== page state (persistent) ======

    def get_current_page(self) -> Optional[str]:
        value = self.get(UserDataPageKey.CURRENT_PAGE)
        return normalize_key(value) if value is not None else None

    def set_current_page(self, name: Any) -> None:
        self.set(UserDataPageKey.CURRENT_PAGE, normalize_key(name))

    def reset_current_page(self) -> None:
        self.pop(UserDataPageKey.CURRENT_PAGE)

    def get_page_history(self) -> list[str]:
        raw = self.get(UserDataPageKey.PAGE_HISTORY, [])
        history = ensure_page_history(raw)
        # Store back if malformed.
        if raw is not history:
            self.set(UserDataPageKey.PAGE_HISTORY, history)
        return history

    def set_page_history(self, history: list[str]) -> None:
        self.set(UserDataPageKey.PAGE_HISTORY, [str(x) for x in history])

    def push_page_to_history(self, page_name: str) -> None:
        name = normalize_key(page_name)
        history = self.get_page_history()
        if not history or history[-1] != name:
            history.append(name)
            self.set_page_history(history)

    def get_previous_page(self) -> Optional[str]:
        history = self.get_page_history()
        return history[-2] if len(history) >= 2 else None

    def pop_last_page(self) -> Optional[str]:
        history = self.get_page_history()
        if not history:
            return None
        last = history.pop()
        self.set_page_history(history)
        return last