from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from .errors import InvalidNodeConfigurationError


class ConditionEvaluator:
    """Small allow-listed condition language. It intentionally never calls eval()."""

    def __init__(self) -> None:
        self._operators: dict[str, Callable[[Any, Any], bool]] = {
            "eq": lambda left, right: left == right,
            "==": lambda left, right: left == right,
            "ne": lambda left, right: left != right,
            "!=": lambda left, right: left != right,
            "gt": lambda left, right: self._ordered(left, right, lambda a, b: a > b),
            ">": lambda left, right: self._ordered(left, right, lambda a, b: a > b),
            "gte": lambda left, right: self._ordered(left, right, lambda a, b: a >= b),
            ">=": lambda left, right: self._ordered(left, right, lambda a, b: a >= b),
            "lt": lambda left, right: self._ordered(left, right, lambda a, b: a < b),
            "<": lambda left, right: self._ordered(left, right, lambda a, b: a < b),
            "lte": lambda left, right: self._ordered(left, right, lambda a, b: a <= b),
            "<=": lambda left, right: self._ordered(left, right, lambda a, b: a <= b),
            "contains": self._contains,
            "not_contains": lambda left, right: not self._contains(left, right),
            "in": lambda left, right: self._contains(right, left),
            "not_in": lambda left, right: not self._contains(right, left),
            "starts_with": lambda left, right: str(left).startswith(str(right)),
            "ends_with": lambda left, right: str(left).endswith(str(right)),
            "exists": lambda left, _right: left is not None,
            "not_exists": lambda left, _right: left is None,
            "truthy": lambda left, _right: bool(left),
            "falsy": lambda left, _right: not bool(left),
        }

    @property
    def supported_operators(self) -> tuple[str, ...]:
        return tuple(sorted(self._operators))

    def evaluate(self, expression: Mapping[str, Any], variables: Mapping[str, Any]) -> bool:
        operator = str(expression.get("operator", expression.get("op", "eq"))).casefold()
        fn = self._operators.get(operator)
        if fn is None:
            raise InvalidNodeConfigurationError(
                f"Unsupported condition operator '{operator}'. "
                f"Allowed: {', '.join(self.supported_operators)}"
            )

        left = self._operand(expression, "left", variables)
        if "variable" in expression and "left" not in expression:
            left = self._lookup(variables, str(expression["variable"]))
        right = self._operand(expression, "right", variables)
        if "value" in expression and "right" not in expression:
            right = expression["value"]
        return bool(fn(left, right))

    def _operand(
        self,
        expression: Mapping[str, Any],
        side: str,
        variables: Mapping[str, Any],
    ) -> Any:
        value = expression.get(side)
        if isinstance(value, Mapping):
            if "variable" in value:
                return self._lookup(variables, str(value["variable"]))
            if "value" in value:
                return value["value"]
        return value

    @staticmethod
    def _lookup(variables: Mapping[str, Any], key: str) -> Any:
        if key in variables:
            return variables[key]
        current: Any = variables
        for part in key.split("."):
            if not isinstance(current, Mapping) or part not in current:
                return None
            current = current[part]
        return current

    @staticmethod
    def _contains(container: Any, item: Any) -> bool:
        if container is None:
            return False
        if isinstance(container, (str, Mapping, Sequence, set, frozenset)):
            return item in container
        return False

    @staticmethod
    def _ordered(left: Any, right: Any, compare: Callable[[Any, Any], bool]) -> bool:
        try:
            return compare(left, right)
        except TypeError:
            try:
                return compare(Decimal(str(left)), Decimal(str(right)))
            except (InvalidOperation, TypeError, ValueError) as exc:
                raise InvalidNodeConfigurationError(
                    f"Values are not order-comparable: {left!r}, {right!r}"
                ) from exc

