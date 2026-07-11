from __future__ import annotations

import unittest

from app.domain.enums import NodeType, TransitionKind
from app.domain.flow import Flow, Node, Transition
from app.runtime.conditions import ConditionEvaluator
from app.runtime.errors import AmbiguousTransitionError, MissingTransitionError
from app.runtime.input_validation import InputValidator
from app.runtime.templating import StrictTemplateRenderer, TemplateRenderError
from app.runtime.transitions import TransitionResolver


class TemplateTests(unittest.TestCase):
    def test_dotted_session_variables_are_available_as_nested_context(self) -> None:
        renderer = StrictTemplateRenderer()
        self.assertEqual(
            renderer.render("Hello {{ user.name }}!", {"user.name": "Ada"}),
            "Hello Ada!",
        )

    def test_missing_variable_is_a_hard_error(self) -> None:
        with self.assertRaises(TemplateRenderError):
            StrictTemplateRenderer().render("{{ missing }}", {})


class InputValidatorTests(unittest.TestCase):
    def test_types_regex_and_range(self) -> None:
        validator = InputValidator()
        self.assertEqual(validator.validate("42", {"type": "integer"}).value, 42)
        self.assertEqual(validator.validate("yes", {"type": "boolean"}).value, True)
        self.assertFalse(
            validator.validate("4", {"type": "integer", "min": 5}).accepted
        )
        self.assertFalse(
            validator.validate("11", {"type": "integer", "max_value": 10}).accepted
        )
        self.assertFalse(
            validator.validate("abc", {"type": "string", "regex": r"\d+"}).accepted
        )


class ConditionTests(unittest.TestCase):
    def test_allowlisted_operators_and_nested_lookup(self) -> None:
        evaluator = ConditionEvaluator()
        self.assertTrue(
            evaluator.evaluate(
                {"variable": "request.total", "operator": ">=", "value": 10},
                {"request.total": 12},
            )
        )
        with self.assertRaisesRegex(Exception, "Unsupported condition operator"):
            evaluator.evaluate(
                {"variable": "x", "operator": "__import__", "value": "os"},
                {"x": 1},
            )


class TransitionResolverTests(unittest.TestCase):
    def test_missing_and_ambiguous_edges_are_typed_errors(self) -> None:
        flow = Flow(
            id="flow",
            name="Flow",
            nodes=(
                Node(id="a", type=NodeType.START),
                Node(id="b", type=NodeType.END),
                Node(id="c", type=NodeType.END),
            ),
            transitions=(
                Transition("t1", "a", "b", TransitionKind.AUTOMATIC),
                Transition("t2", "a", "c", TransitionKind.AUTOMATIC),
            ),
        )
        resolver = TransitionResolver()
        with self.assertRaises(AmbiguousTransitionError):
            resolver.resolve(flow, "a", kinds=(TransitionKind.AUTOMATIC,))
        with self.assertRaises(MissingTransitionError):
            resolver.resolve(flow, "b", kinds=(TransitionKind.AUTOMATIC,))


if __name__ == "__main__":
    unittest.main()
