from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.enums.background_task_enums import RecurringTaskStatus

from pipubot.background.types.task_types import PipubotTaskType


@dataclass(frozen=True, slots=True)
class RecurringSpec:
    key: str
    task_type: str
    interval_seconds: int
    payload_template: dict
    max_runs: Optional[int] = None
    status: RecurringTaskStatus = RecurringTaskStatus.ACTIVE
    first_run_at = None


SYSTEM_RECURRING_SPECS = [
    RecurringSpec(
        key="system.print_hello.10s",
        task_type=str(PipubotTaskType.PRINT_HELLO),
        interval_seconds=10,
        payload_template={"message": "Hello every 10 seconds 🚀"},
    ),
]