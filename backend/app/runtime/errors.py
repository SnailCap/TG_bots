from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class RuntimeErrorContext:
    project_id: str | None = None
    flow_id: str | None = None
    node_id: str | None = None
    session_id: str | None = None
    details: Mapping[str, Any] | None = None


class BotRuntimeError(RuntimeError):
    code = "runtime_error"

    def __init__(self, message: str, *, context: RuntimeErrorContext | None = None) -> None:
        super().__init__(message)
        self.context = context or RuntimeErrorContext()


class FlowNotFoundError(BotRuntimeError):
    code = "flow_not_found"


class NodeNotFoundError(BotRuntimeError):
    code = "node_not_found"


class InvalidNodeConfigurationError(BotRuntimeError):
    code = "invalid_node_configuration"


class TransitionResolutionError(BotRuntimeError):
    code = "transition_resolution_error"


class MissingTransitionError(TransitionResolutionError):
    code = "missing_transition"


class AmbiguousTransitionError(TransitionResolutionError):
    code = "ambiguous_transition"


class ExecutionGuardError(BotRuntimeError):
    code = "execution_guard_exceeded"


class InputRejectedError(BotRuntimeError):
    code = "input_rejected"


class ActionDiscoveryError(BotRuntimeError):
    code = "action_discovery_error"


class ActionNotFoundError(BotRuntimeError):
    code = "action_not_found"


class ActionExecutionError(BotRuntimeError):
    code = "action_execution_error"


class ActionTimeoutError(ActionExecutionError):
    code = "action_timeout"


class InvalidActionResultError(ActionExecutionError):
    code = "invalid_action_result"


class RuntimeValidationError(BotRuntimeError):
    code = "runtime_validation_failed"

