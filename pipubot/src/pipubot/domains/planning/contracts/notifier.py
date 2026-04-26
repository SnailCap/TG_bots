from typing import Protocol


class PlanningNotifier(Protocol):
    async def send_task_reminder(
        self,
        *,
        user_id: int,
        task_title: str,
        message: str,
    ) -> None: ...