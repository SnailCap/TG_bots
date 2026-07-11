from __future__ import annotations

from collections.abc import Iterable

from app.domain.enums import TransitionKind
from app.domain.flow import Flow, Transition

from .errors import (
    AmbiguousTransitionError,
    MissingTransitionError,
    RuntimeErrorContext,
)


class TransitionResolver:
    """Resolve graph edges without silently picking an ambiguous branch."""

    def outgoing(self, flow: Flow, node_id: str) -> tuple[Transition, ...]:
        return tuple(
            transition
            for transition in flow.transitions
            if transition.source_node_id == node_id
        )

    def resolve(
        self,
        flow: Flow,
        node_id: str,
        *,
        kinds: Iterable[TransitionKind] | None = None,
        outcome: str | None = None,
    ) -> Transition:
        allowed = set(kinds) if kinds is not None else None
        candidates = [
            transition
            for transition in self.outgoing(flow, node_id)
            if allowed is None or transition.kind in allowed
        ]

        if outcome is not None:
            normalized = str(outcome).strip().casefold()
            candidates = [
                transition
                for transition in candidates
                if normalized in self._selectors(transition)
            ]

        context = RuntimeErrorContext(
            flow_id=flow.id,
            node_id=node_id,
            details={
                "kinds": sorted(kind.value for kind in allowed) if allowed else None,
                "outcome": outcome,
            },
        )
        if not candidates:
            raise MissingTransitionError(
                f"Node '{node_id}' has no matching outgoing transition",
                context=context,
            )
        if len(candidates) > 1:
            raise AmbiguousTransitionError(
                f"Node '{node_id}' has {len(candidates)} matching outgoing transitions: "
                + ", ".join(transition.id for transition in candidates),
                context=context,
            )
        return candidates[0]

    @staticmethod
    def _selectors(transition: Transition) -> set[str]:
        values = {
            transition.outcome,
            transition.label,
            transition.config.get("value"),
            transition.config.get("trigger"),
            transition.config.get("branch"),
            transition.config.get("key"),
        }
        return {
            str(value).strip().casefold()
            for value in values
            if value is not None and str(value).strip()
        }

