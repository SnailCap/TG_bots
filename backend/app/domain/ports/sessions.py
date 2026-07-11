from __future__ import annotations

from typing import Any, Protocol, Sequence

from ..runtime import RuntimeHistoryEntry
from ..session import Session


class SessionRepository(Protocol):
    def get(self, session_id: str) -> Session | None: ...

    def find_active(
        self,
        project_id: str,
        telegram_user_id: int,
        telegram_chat_id: int,
    ) -> Session | None: ...

    def save(self, session: Session) -> None: ...
    def delete(self, session_id: str) -> None: ...
    def list_for_project(self, project_id: str) -> Sequence[Session]: ...


class RuntimeStorage(Protocol):
    def append_history(self, entry: RuntimeHistoryEntry) -> RuntimeHistoryEntry: ...

    def list_history(
        self,
        project_id: str,
        *,
        session_id: str | None = None,
        limit: int = 200,
        after_id: int | None = None,
    ) -> Sequence[RuntimeHistoryEntry]: ...

    def set_kv(self, project_id: str, key: str, value: Any) -> None: ...
    def get_kv(self, project_id: str, key: str, default: Any = None) -> Any: ...
    def delete_kv(self, project_id: str, key: str) -> None: ...

