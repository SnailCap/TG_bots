from pathlib import Path

from tg_bot_core.project import ProjectLoader, validate_project


def test_project_resources_are_valid() -> None:
    root = Path(__file__).resolve().parents[1]
    diagnostics = validate_project(ProjectLoader().load(root), inspect_code=True)
    assert not [item for item in diagnostics if item.level == "error"]


def test_entrypoint_imports() -> None:
    __import__("visual_template_qa.__main__")
