from __future__ import annotations

import argparse
from pathlib import Path

from .project import load_and_validate_project


def validate_command(root: Path) -> int:
    _project, diagnostics = load_and_validate_project(root, inspect_code=True)
    for item in diagnostics:
        location = f" [{item.source_path}]" if item.source_path else ""
        print(f"{item.level.upper()} {item.code}{location}: {item.message}")
    return 1 if any(item.level == "error" for item in diagnostics) else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tg_bot_core")
    subcommands = parser.add_subparsers(dest="command", required=True)
    validate_parser = subcommands.add_parser("validate", help="validate a bot project")
    validate_parser.add_argument("project", nargs="?", default=".")
    arguments = parser.parse_args(argv)
    if arguments.command == "validate":
        return validate_command(Path(arguments.project).resolve())
    return 2
