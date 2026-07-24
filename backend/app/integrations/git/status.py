from __future__ import annotations

import re
from pathlib import Path

from .command_runner import GitCommandRunner


_STATUS_KIND = {
    "M": "modified",
    "A": "added",
    "D": "deleted",
    "R": "renamed",
    "C": "added",
    "?": "untracked",
}


def parse_porcelain(raw: str) -> list[dict]:
    entries = raw.split("\0")
    changes: list[dict] = []
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if not entry:
            continue
        code = entry[:2]
        path = entry[3:]
        old_path = None
        if "R" in code and index < len(entries):
            old_path, index = path, index + 1
            path = entries[index - 1]
        marker = "?" if code == "??" else next((item for item in code if item != " "), "M")
        changes.append({
            "path": path.replace("\\", "/"),
            "old_path": old_path,
            "status": _STATUS_KIND.get(marker, "modified"),
            "staged": code[0] not in (" ", "?"),
        })
    return changes


def semantic_summary(change: dict) -> str:
    path = change["path"]
    status = change["status"]
    label = {"modified": "updated", "added": "added", "deleted": "removed", "renamed": "renamed", "untracked": "added"}.get(status, status)
    patterns = (
        (r"^resources/templates/views/(.+)\.txt$", "View text"),
        (r"^resources/templates/(.+)\.txt$", "Template"),
        (r"^resources/views/(.+)\.json$", "View"),
        (r"^resources/flows/(.+)\.json$", "Flow"),
        (r"^resources/schedules/(.+)\.json$", "Schedule"),
        (r"^resources/handlers\.json$", "Handler bindings"),
        (r"^resources/commands\.json$", "Commands"),
        (r"^resources/bot\.json$", "Project settings"),
    )
    for pattern, entity in patterns:
        match = re.match(pattern, path)
        if match:
            name = match.group(1) if match.groups() else ""
            return f'{entity}{f" “{name}”" if name else ""} {label}'
    return f"{path} {label}"


def collect_changes(root: Path, runner: GitCommandRunner, *, include_diff: bool = True) -> list[dict]:
    parsed = parse_porcelain(runner.run(root, ["status", "--porcelain=v1", "-z", "--untracked-files=all"]).stdout)
    has_head = runner.run(root, ["rev-parse", "--verify", "HEAD"], check=False).returncode == 0
    for change in parsed:
        change["summary"] = semantic_summary(change)
        change["binary"] = False
        change["diff"] = None
        if not include_diff or change["status"] == "untracked":
            continue
        result = runner.run(
            root,
            ["diff", "--no-ext-diff", "--no-color", "--unified=3", *(["HEAD"] if has_head else []), "--", change["path"]],
            check=False,
        )
        text = result.stdout
        if "Binary files " in text or "GIT binary patch" in text:
            change["binary"] = True
        else:
            change["diff"] = text[:200_000] or None
    return parsed
