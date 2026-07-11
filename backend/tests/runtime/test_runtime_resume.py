from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.domain.enums import NodeType, RuntimeState, SessionStatus, TransitionKind
from app.domain.flow import Flow, Node, Transition
from app.runtime.transport import IncomingUpdate, UpdateKind
from tests.fakes.telegram import FakeTelegramPort
from tests.runtime.support import build_harness


def resume_flow() -> Flow:
    return Flow(
        id="resume-flow",
        name="Resume",
        start_node_id="start",
        nodes=(
            Node(id="start", type=NodeType.START, name="Start"),
            Node(
                id="ask",
                type=NodeType.ASK_INPUT,
                name="Ask name",
                config={
                    "prompt": "What is your name?",
                    "variable_name": "user.name",
                    "input_type": "string",
                    "required": True,
                },
            ),
            Node(
                id="hello",
                type=NodeType.SEND_MESSAGE,
                config={"text": "Hello {{ user.name }}!"},
            ),
            Node(id="end", type=NodeType.END),
        ),
        transitions=(
            Transition("t-start", "start", "ask", TransitionKind.AUTOMATIC),
            Transition("t-input", "ask", "hello", TransitionKind.INPUT),
            Transition("t-end", "hello", "end", TransitionKind.AUTOMATIC),
        ),
    )


class RuntimeResumeTests(unittest.IsolatedAsyncioTestCase):
    async def test_session_resumes_from_sqlite_after_runtime_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            first = build_harness(root, resume_flow())
            status = await first.service.start()
            self.assertEqual(status.state, RuntimeState.RUNNING)
            await first.telegram.emit(
                IncomingUpdate(
                    update_id=1,
                    telegram_user_id=7,
                    telegram_chat_id=7,
                    kind=UpdateKind.COMMAND,
                    command="start",
                    text="/start",
                )
            )
            active = first.runtime.find_active(first.project.id, 7, 7)
            self.assertIsNotNone(active)
            assert active is not None
            self.assertEqual(active.current_node_id, "ask")
            self.assertEqual(active.status, SessionStatus.WAITING_INPUT)
            self.assertEqual(first.telegram.messages[-1].text, "What is your name?")
            await first.service.stop()

            second_telegram = FakeTelegramPort(first.project.configuration.identity)
            second = build_harness(
                root,
                resume_flow(),
                telegram=second_telegram,
                project=first.project,
            )
            await second.service.start()
            await second.telegram.emit(
                IncomingUpdate(
                    update_id=2,
                    telegram_user_id=7,
                    telegram_chat_id=7,
                    kind=UpdateKind.MESSAGE,
                    text="Ada",
                )
            )
            sessions = second.runtime.list_for_project(second.project.id)
            restored = next(item for item in sessions if item.id == active.id)
            self.assertEqual(restored.status, SessionStatus.COMPLETED)
            self.assertEqual(restored.variables["user.name"], "Ada")
            self.assertEqual(second.telegram.messages[-1].text, "Hello Ada!")
            await second.service.stop()


if __name__ == "__main__":
    unittest.main()

