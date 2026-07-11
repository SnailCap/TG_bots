from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.domain.enums import NodeType, RuntimeState, SessionStatus, TransitionKind
from app.domain.flow import Flow, Node, Transition
from app.runtime.transport import IncomingUpdate, MediaKind, UpdateKind
from tests.runtime.support import build_harness


def vertical_flow() -> Flow:
    return Flow(
        id="vertical-flow",
        name="Vertical scenario",
        start_node_id="start",
        nodes=(
            Node("start", NodeType.START),
            Node(
                "ask-name",
                NodeType.ASK_INPUT,
                config={"prompt": "Your name?", "variable_name": "user.name"},
            ),
            Node(
                "choice",
                NodeType.CHOICE,
                config={
                    "prompt": "Hello {{ user.name }}. What next?",
                    "choices": [
                        {"id": "option-create", "label": "Create request", "value": "create"},
                        {"id": "option-about", "label": "About", "value": "about"},
                    ],
                },
            ),
            Node(
                "ask-description",
                NodeType.ASK_INPUT,
                config={
                    "prompt": "Describe the request",
                    "variable_name": "request.description",
                    "min_length": 3,
                },
            ),
            Node(
                "create-request",
                NodeType.ACTION,
                config={
                    "action_name": "create_request",
                    "timeout_seconds": 2,
                    "input_parameters": {
                        "description": "{{ request.description }}",
                        "requester": {"name": "{{ user.name }}"},
                    },
                },
            ),
            Node(
                "created",
                NodeType.SEND_MESSAGE,
                config={"text": "Request {{ request.id }} created for {{ user.name }}"},
            ),
            Node(
                "about",
                NodeType.SEND_MESSAGE,
                config={"text": "This is the project description."},
            ),
            Node("end", NodeType.END),
        ),
        transitions=(
            Transition("t1", "start", "ask-name", TransitionKind.AUTOMATIC),
            Transition("t2", "ask-name", "choice", TransitionKind.INPUT),
            Transition(
                "t3",
                "choice",
                "ask-description",
                TransitionKind.BUTTON,
                outcome="option-create",
            ),
            Transition(
                "t4",
                "choice",
                "about",
                TransitionKind.BUTTON,
                outcome="option-about",
            ),
            Transition("t5", "ask-description", "create-request", TransitionKind.INPUT),
            Transition("t6", "create-request", "created", TransitionKind.SUCCESS),
            Transition("t7", "created", "end", TransitionKind.AUTOMATIC),
            Transition("t8", "about", "end", TransitionKind.AUTOMATIC),
        ),
    )


class VerticalRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_action_result_is_logged_and_uses_error_edge(self) -> None:
        flow = Flow(
            id="invalid-result-flow",
            name="Invalid action result",
            start_node_id="start",
            nodes=(
                Node("start", NodeType.START),
                Node("action", NodeType.ACTION, config={"action_name": "invalid"}),
                Node("recover", NodeType.SEND_MESSAGE, config={"text": "Recovered"}),
                Node("end", NodeType.END),
            ),
            transitions=(
                Transition("a", "start", "action", TransitionKind.AUTOMATIC),
                Transition("b", "action", "recover", TransitionKind.ERROR),
                Transition("c", "recover", "end", TransitionKind.AUTOMATIC),
            ),
        )
        with tempfile.TemporaryDirectory() as temporary:
            harness = build_harness(Path(temporary) / "project", flow)
            (harness.root / "scripts" / "actions.py").write_text(
                """
from bot_engine import action

@action("invalid")
async def invalid(context):
    return {"not": "an ActionResult"}
""".strip(),
                encoding="utf-8",
            )
            await harness.service.start()
            await harness.telegram.emit(
                IncomingUpdate(1, 8, 8, UpdateKind.COMMAND, text="/start", command="start")
            )

            session = harness.runtime.list_for_project(harness.project.id)[0]
            self.assertEqual(session.status, SessionStatus.COMPLETED)
            self.assertEqual(harness.telegram.messages[-1].text, "Recovered")
            action_error = next(
                entry
                for entry in harness.runtime.list_history(harness.project.id)
                if entry.event_type == "action.error"
            )
            self.assertIn("returned dict", action_error.message)
            await harness.service.stop()

    async def test_media_asset_and_flat_keyboard_are_sent(self) -> None:
        flow = Flow(
            id="media-flow",
            name="Media",
            start_node_id="start",
            nodes=(
                Node("start", NodeType.START),
                Node(
                    "welcome",
                    NodeType.SEND_MESSAGE,
                    config={
                        "text": "Welcome",
                        "media": {
                            "type": "photo",
                            "path": "welcome.jpg",
                            "source_type": "asset",
                        },
                        "keyboard": ["One", "Two"],
                    },
                ),
                Node("end", NodeType.END),
            ),
            transitions=(
                Transition("a", "start", "welcome", TransitionKind.AUTOMATIC),
                Transition("b", "welcome", "end", TransitionKind.AUTOMATIC),
            ),
        )
        with tempfile.TemporaryDirectory() as temporary:
            harness = build_harness(Path(temporary) / "project", flow)
            asset = harness.root / "assets" / "welcome.jpg"
            asset.write_bytes(b"fake-image")
            await harness.service.start()

            await harness.telegram.emit(
                IncomingUpdate(1, 3, 3, UpdateKind.COMMAND, text="/start", command="start")
            )

            message = harness.telegram.messages[-1]
            self.assertEqual(message.media_kind, MediaKind.PHOTO)
            self.assertEqual(message.media, str(asset.resolve()))
            self.assertEqual(message.caption, "Welcome")
            assert message.keyboard is not None
            self.assertEqual(
                [[button.text for button in row] for row in message.keyboard.rows],
                [["One"], ["Two"]],
            )
            await harness.service.stop()

    async def test_ask_choice_action_template_and_end(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            harness = build_harness(Path(temporary) / "project", vertical_flow())
            (harness.root / "scripts" / "actions.py").write_text(
                """
from bot_engine import action, ActionContext, ActionResult
from helper import make_request_id

@action("create_request")
async def create_request(context: ActionContext) -> ActionResult:
    assert context.variables["request.description"] == "Need help"
    assert context.parameters == {
        "description": "Need help",
        "requester": {"name": "Ada"},
    }
    return ActionResult.success(variables={"request.id": make_request_id()})
""".strip(),
                encoding="utf-8",
            )
            (harness.root / "scripts" / "helper.py").write_text(
                'def make_request_id():\n    return "REQ-42"\n',
                encoding="utf-8",
            )
            await harness.service.start()

            await harness.telegram.emit(
                IncomingUpdate(1, 5, 5, UpdateKind.COMMAND, text="/start", command="start")
            )
            await harness.telegram.emit(
                IncomingUpdate(2, 5, 5, UpdateKind.MESSAGE, text="Ada")
            )
            choice_message = harness.telegram.messages[-1]
            assert choice_message.keyboard is not None
            self.assertEqual(
                choice_message.keyboard.rows[0][0].value,
                "svc:flow:option-create",
            )
            await harness.telegram.emit(
                IncomingUpdate(
                    3,
                    5,
                    5,
                    UpdateKind.CALLBACK,
                    callback_data="svc:flow:option-create",
                )
            )
            await harness.telegram.emit(
                IncomingUpdate(4, 5, 5, UpdateKind.MESSAGE, text="Need help")
            )

            session = harness.runtime.list_for_project(harness.project.id)[0]
            self.assertEqual(session.status, SessionStatus.COMPLETED)
            self.assertEqual(session.variables["user.name"], "Ada")
            self.assertEqual(session.variables["request.description"], "Need help")
            self.assertEqual(session.variables["request.id"], "REQ-42")
            self.assertEqual(
                harness.telegram.messages[-1].text,
                "Request REQ-42 created for Ada",
            )
            self.assertTrue(
                any(
                    entry.event_type == "action.completed"
                    for entry in harness.runtime.list_history(harness.project.id)
                )
            )
            await harness.service.stop()

    async def test_action_exception_uses_error_edge_without_stopping_bot(self) -> None:
        flow = Flow(
            id="error-flow",
            name="Error branch",
            start_node_id="start",
            nodes=(
                Node("start", NodeType.START),
                Node("action", NodeType.ACTION, config={"action_name": "explode"}),
                Node("recover", NodeType.SEND_MESSAGE, config={"text": "Recovered"}),
                Node("end", NodeType.END),
            ),
            transitions=(
                Transition("a", "start", "action", TransitionKind.AUTOMATIC),
                Transition("b", "action", "recover", TransitionKind.ERROR),
                Transition("c", "recover", "end", TransitionKind.AUTOMATIC),
            ),
        )
        with tempfile.TemporaryDirectory() as temporary:
            harness = build_harness(Path(temporary) / "project", flow)
            (harness.root / "scripts" / "actions.py").write_text(
                """
from bot_engine import action

@action("explode")
async def explode(context):
    raise RuntimeError("boom")
""".strip(),
                encoding="utf-8",
            )
            await harness.service.start()
            await harness.telegram.emit(
                IncomingUpdate(1, 9, 9, UpdateKind.COMMAND, text="/start", command="start")
            )
            session = harness.runtime.list_for_project(harness.project.id)[0]
            self.assertEqual(session.status, SessionStatus.COMPLETED)
            self.assertIn("boom", session.metadata["last_action_error"])
            self.assertEqual(harness.telegram.messages[-1].text, "Recovered")
            self.assertEqual(harness.service.status.state, RuntimeState.RUNNING)
            action_error = next(
                entry
                for entry in harness.runtime.list_history(harness.project.id)
                if entry.event_type == "action.error"
            )
            self.assertEqual(action_error.context["script_path"], "scripts/actions.py")
            self.assertIsInstance(action_error.context["line"], int)
            self.assertEqual(action_error.context["flow_id"], "error-flow")
            self.assertEqual(action_error.context["node_id"], "action")
            await harness.service.stop()


if __name__ == "__main__":
    unittest.main()
