from enum import StrEnum


class NodeType(StrEnum):
    START = "start"
    SEND_MESSAGE = "send_message"
    ASK_INPUT = "ask_input"
    CHOICE = "choice"
    ACTION = "action"
    CONDITION = "condition"
    END = "end"


class TransitionKind(StrEnum):
    AUTOMATIC = "automatic"
    INPUT = "input"
    BUTTON = "button"
    CONDITION = "condition"
    ACTION = "action"
    SUCCESS = "success"
    ERROR = "error"


class SessionStatus(StrEnum):
    ACTIVE = "active"
    WAITING_INPUT = "waiting_input"
    COMPLETED = "completed"
    FAILED = "failed"
    RESET = "reset"


class VariableType(StrEnum):
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    JSON = "json"


class ActionResultStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"
    BRANCH = "branch"


class RuntimeState(StrEnum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class ValidationSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

