from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.runtime.actions import ProjectActionLoader


class ProjectActionImportTests(unittest.IsolatedAsyncioTestCase):
    async def test_sibling_imports_are_isolated_between_projects(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            roots = [base / "first", base / "second"]
            values = ["FIRST", "SECOND"]
            for root, value in zip(roots, values, strict=True):
                scripts = root / "scripts"
                scripts.mkdir(parents=True)
                (scripts / "helper.py").write_text(
                    f'VALUE = "{value}"\n',
                    encoding="utf-8",
                )
                (scripts / "actions.py").write_text(
                    """
from bot_engine import action, ActionResult
from helper import VALUE

@action("which_project")
async def which_project(context):
    return ActionResult.success(variables={"value": VALUE})
""".strip(),
                    encoding="utf-8",
                )

            loader = ProjectActionLoader()
            first = loader.registry("first", roots[0]).require("which_project")
            second = loader.registry("second", roots[1]).require("which_project")

            self.assertEqual((await first.function(None)).variables["value"], "FIRST")
            self.assertEqual((await second.function(None)).variables["value"], "SECOND")


if __name__ == "__main__":
    unittest.main()
