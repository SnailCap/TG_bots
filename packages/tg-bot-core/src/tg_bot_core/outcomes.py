from __future__ import annotations

from .handlers import HandlerExecutionError
from .project import ActionSpec, HandlerInvocation
from .sdk import HandlerResult


class OutcomeRouter:
    """Resolve business outcomes exclusively through declarative project routes."""

    def route(self, invocation: HandlerInvocation, result: HandlerResult) -> ActionSpec | None:
        route = invocation.outcomes.get(result.outcome_name)
        if route is None and result.outcome_name != "success":
            raise HandlerExecutionError(
                f"Handler '{invocation.handler}' outcome '{result.outcome_name}' has no declarative route."
            )
        return route
