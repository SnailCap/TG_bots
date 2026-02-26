from enum import Enum


class UserDataPageKey(str, Enum):
    PAGE_HISTORY = "page_history"
    CURRENT_PAGE = "current_page"
    NAME = "name"


class UserDataProcessKey(str, Enum):
    CURRENT_PROCESS = "current_process"
    FINISHED_PROCESS = "finished_process"
    CANCELED_PROCESS = "canceled_process"
    NEXT_STEP_REQUESTED = "next_step_requested"
    PROCESSES = "process"
