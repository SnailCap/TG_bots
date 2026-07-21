from __future__ import annotations

import argparse
import os
from pathlib import Path

from tg_bot_core import BotApp, BotConfig
from tg_bot_core.project import ProjectLoader, validate_project


def project_root() -> Path:
    override = os.getenv("BOT_PROJECT_ROOT")
    if override:
        candidate = Path(override).expanduser().resolve()
        if (candidate / "resources" / "bot.json").is_file():
            return candidate
        raise RuntimeError(f"BOT_PROJECT_ROOT does not contain resources/bot.json: {candidate}")
    for candidate in (Path.cwd().resolve(), Path(__file__).resolve().parents[2]):
        if (candidate / "resources" / "bot.json").is_file():
            return candidate
    raise RuntimeError(
        "Cannot locate the bot project. Run from its root or set BOT_PROJECT_ROOT."
    )


def validate(root: Path) -> int:
    project = ProjectLoader().load(root)
    diagnostics = validate_project(project, inspect_code=True)
    for diagnostic in diagnostics:
        source = f" [{diagnostic.source_path}]" if diagnostic.source_path else ""
        print(f"{diagnostic.level.upper()} {diagnostic.code}{source}: {diagnostic.message}")
    return 1 if any(item.level == "error" for item in diagnostics) else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate", action="store_true", help="validate resources and handler bindings")
    args = parser.parse_args(argv)
    root = project_root()
    if args.validate:
        return validate(root)
    BotApp(config=BotConfig.from_env(project_root=root), services=[]).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
