from __future__ import annotations

import unittest

from app.application.validation import FlowValidator
from app.domain.enums import NodeType, TransitionKind
from app.domain.flow import Flow, Node, Transition


class FlowValidatorContractTests(unittest.TestCase):
    def test_media_mapping_is_valid_send_message_content(self) -> None:
        flow = Flow(
            id="media-flow",
            name="Media flow",
            start_node_id="start",
            nodes=(
                Node("start", NodeType.START),
                Node(
                    "media",
                    NodeType.SEND_MESSAGE,
                    config={
                        "media": {
                            "type": "photo",
                            "path": "welcome.jpg",
                            "source_type": "asset",
                        }
                    },
                ),
                Node("end", NodeType.END),
            ),
            transitions=(
                Transition("a", "start", "media", TransitionKind.AUTOMATIC),
                Transition("b", "media", "end", TransitionKind.AUTOMATIC),
            ),
        )

        codes = {issue.code for issue in FlowValidator().validate(flow)}
        self.assertNotIn("send_message.content_missing", codes)


if __name__ == "__main__":
    unittest.main()
