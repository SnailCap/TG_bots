from __future__ import annotations

import ast
import json
import keyword
import re
import shutil
import tempfile
from pathlib import Path

from tg_bot_core.project import ProjectLoader, validate_project

from .repository import WorkspaceError


_WINDOWS_RESERVED = {
    "con", "prn", "aux", "nul", "clock$",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
}


class StarterScaffolder:
    """Build a complete project in a sibling staging directory, then publish it."""

    def __init__(self, loader: ProjectLoader | None = None) -> None:
        self._loader = loader or ProjectLoader()

    def create(self, *, parent_path: str, name: str, package_name: str | None = None) -> Path:
        parent = Path(parent_path).expanduser().resolve(strict=False)
        if not parent.is_dir():
            raise WorkspaceError("Choose an existing parent directory.")
        parts = re.findall(r"[A-Za-z0-9]+", name.lower())
        if not parts:
            raise WorkspaceError("Project name must contain ASCII letters or digits.")
        slug = "-".join(parts)
        package = package_name or "_".join(parts)
        self._validate_names(slug, package)
        target = parent / slug
        if target.exists():
            raise WorkspaceError(f"Project directory already exists: {slug}")

        staging = Path(tempfile.mkdtemp(prefix=f".{slug}.studio-", dir=parent))
        published = False
        try:
            self._populate(staging, slug, package)
            project = self._loader.load(staging)
            errors = [item for item in validate_project(project, inspect_code=True) if item.level == "error"]
            if errors:
                raise WorkspaceError("Generated starter is invalid: " + "; ".join(item.message for item in errors))
            for source in (staging / "src").rglob("*.py"):
                ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
            if target.exists():
                raise WorkspaceError(f"Project directory already exists: {slug}")
            staging.rename(target)
            published = True
            return target
        except WorkspaceError:
            raise
        except (OSError, SyntaxError, ValueError) as error:
            raise WorkspaceError(f"Could not create starter project: {error}") from error
        finally:
            if not published:
                shutil.rmtree(staging, ignore_errors=True)

    @staticmethod
    def _validate_names(slug: str, package: str) -> None:
        if slug.lower() in _WINDOWS_RESERVED:
            raise WorkspaceError("Project name is reserved by the operating system.")
        if not package.isidentifier() or keyword.iskeyword(package):
            raise WorkspaceError("Package name must be a non-keyword Python identifier.")
        if package.lower() in _WINDOWS_RESERVED:
            raise WorkspaceError("Package name is reserved by the operating system.")

    def _populate(self, root: Path, slug: str, package: str) -> None:
        resources = root / "resources"
        package_root = root / "src" / package
        for directory in (
            resources / "views",
            resources / "flows",
            resources / "schedules",
            resources / "templates",
            package_root / "handlers",
            package_root / "services",
            root / "data",
            root / "tests",
        ):
            directory.mkdir(parents=True, exist_ok=True)

        self._json(resources / "bot.json", {
            "schema_version": 3,
            "id": package,
            "package": package,
            "entry_view": "home",
            "start": {"flow": "home", "policy": "reset"},
        })
        self._json(resources / "handlers.json", {"schema_version": 3, "handlers": []})
        self._json(resources / "commands.json", {"schema_version": 3, "commands": []})
        self._text(resources / "schedules" / ".gitkeep", "")
        self._json(resources / "views" / "home.json", {
            "schema_version": 3,
            "id": "home",
            "text": {"template": "home.txt"},
            "keyboard": [],
        })
        self._json(resources / "flows" / "home.json", {
            "schema_version": 3,
            "id": "home",
            "initial_state": "home",
            "lifecycle": {},
            "states": {"home": {"view": "home", "events": {}}},
        })
        self._text(resources / "templates" / "home.txt", "Welcome to your bot!\n")
        self._text(package_root / "__init__.py", "")
        self._text(package_root / "handlers" / "__init__.py", "")
        self._text(package_root / "services" / "__init__.py", "")
        self._text(package_root / "__main__.py", self._main_module())
        self._text(root / "tests" / "test_project.py", self._project_test(package))
        self._text(root / ".env.example", "BOT_TOKEN=\n")
        self._text(
            root / ".gitignore",
            ".env\n"
            ".venv/\n"
            "data/*.sqlite3\n"
            "data/*.sqlite3-wal\n"
            "data/*.sqlite3-shm\n"
            "__pycache__/\n"
            "*.py[cod]\n"
            ".pytest_cache/\n"
            "*.egg-info/\n"
            ".idea/\n"
            ".vscode/\n"
            ".botstudio/backups/\n"
            ".botstudio/*.credentials*\n"
            "build/\n"
            "dist/\n",
        )
        self._text(root / ".dockerignore", ".env\n.venv/\ndata/\n__pycache__/\n.pytest_cache/\n.git/\n")
        self._text(root / "pyproject.toml", self._pyproject(slug))
        self._text(root / "README.md", self._readme(package))
        self._text(root / "Dockerfile", self._dockerfile(package))

    @staticmethod
    def _json(path: Path, data: dict) -> None:
        StarterScaffolder._text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")

    @staticmethod
    def _text(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")

    @staticmethod
    def _pyproject(slug: str) -> str:
        return f'''[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "{slug}"
version = "0.1.0"
requires-python = ">=3.12,<3.14"
dependencies = [
    "tg-bot-core @ git+https://github.com/SnailCap/TG_bots.git@119f2200566021ebf4d5bafa44c08805dcf236ed#subdirectory=packages/tg-bot-core",
]

[project.optional-dependencies]
dev = ["pytest>=8,<9"]

[tool.setuptools]
package-dir = {{"" = "src"}}

[tool.setuptools.packages.find]
where = ["src"]
'''

    @staticmethod
    def _main_module() -> str:
        return '''from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from tg_bot_core import BotApp, BotConfig
from tg_bot_core.project import ProjectLoader, validate_project


log = logging.getLogger(__name__)


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )


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
    configure_logging()
    root = project_root()
    if args.validate:
        return validate(root)
    log.info("Starting bot project from %s", root)
    try:
        BotApp(config=BotConfig.from_env(project_root=root), services=[]).run()
    except Exception:
        log.exception("Bot process stopped because of an unhandled error.")
        return 1
    finally:
        log.info("Bot process finished.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

    @staticmethod
    def _project_test(package: str) -> str:
        return f'''from pathlib import Path

from tg_bot_core.project import ProjectLoader, validate_project


def test_project_resources_are_valid() -> None:
    root = Path(__file__).resolve().parents[1]
    diagnostics = validate_project(ProjectLoader().load(root), inspect_code=True)
    assert not [item for item in diagnostics if item.level == "error"]


def test_entrypoint_imports() -> None:
    __import__("{package}.__main__")
'''

    @staticmethod
    def _readme(package: str) -> str:
        return f'''# {package}

This is an autonomous Telegram bot project generated by Telegram Bot Studio.
Studio is not required to validate, run, test, or deploy it.

## Local setup

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
```

Set `BOT_TOKEN` in the shell, then run commands from this project directory:

```bash
export BOT_TOKEN="123456:replace-me"
python -m {package} --validate
python -m {package}
pytest
```

PowerShell equivalent: `$env:BOT_TOKEN="123456:replace-me"`. You can also save
`BOT_TOKEN` in a local `.env` file; the runtime reads it automatically, while an
environment variable from the shell or process manager takes precedence. Docker also
uses the same file with `--env-file` below.
If a process manager uses another working directory, set `BOT_PROJECT_ROOT` to this
project directory (or configure its working directory accordingly).

Runtime state is stored in `data/runtime.sqlite3`. Back up that file and mount `data/`
as persistent storage in production.

## Docker

```bash
docker build -t {package} .
docker run --rm --env-file .env -v "$(pwd)/data:/app/data" {package}
```

The core runtime dependency is pinned in `pyproject.toml`. Update it deliberately to a
tested tag or immutable commit when upgrading the runtime.
'''

    @staticmethod
    def _dockerfile(package: str) -> str:
        return f'''FROM python:3.12-slim

RUN apt-get update \\
    && apt-get install -y --no-install-recommends git \\
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app
RUN python -m pip install --no-cache-dir .

VOLUME ["/app/data"]
STOPSIGNAL SIGTERM
CMD ["python", "-m", "{package}"]
'''
