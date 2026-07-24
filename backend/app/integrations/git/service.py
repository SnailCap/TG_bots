from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from app.workspace.repository import WorkspaceRepository

from .command_runner import GitCommandRunner
from .errors import (
    GitNotInstalled,
    IncompatibleHistory,
    ProductionDiverged,
    RemoteChangesDetected,
    RepositoryNotConnected,
    ValidationFailed,
    WorkingTreeDirty,
)
from .github_client import GitHubClient
from .models import (
    GitConnectRequest,
    GitCreateRepositoryRequest,
    GitPublishRequest,
    GitPushRequest,
    GitSettings,
)
from .status import collect_changes
from .validation import ensure_gitignore, scan_for_secrets


class GitService:
    def __init__(
        self,
        repository: WorkspaceRepository,
        validate_project: Callable[[str], list[dict]],
        *,
        runner: GitCommandRunner | None = None,
        github: GitHubClient | None = None,
    ) -> None:
        self.repository = repository
        self.validate_project = validate_project
        self.runner = runner or GitCommandRunner()
        self.github = github or GitHubClient()

    def status(self, project_id: str) -> dict:
        root = self._root(project_id)
        if not (root / ".git").exists() or not self._settings_path(root).is_file():
            return {
                "connected": False,
                "git_installed": self._git_installed(root),
                "repository_detected": (root / ".git").exists(),
            }
        settings = self._settings(root)
        branch = self._branch(root)
        changes = collect_changes(root, self.runner, include_diff=False)
        ahead, behind = self._ahead_behind(root, settings, branch)
        commit = self._last_commit(root)
        return {
            "connected": True,
            "git_installed": True,
            "account": settings.repository.split("/", 1)[0],
            "repository": settings.repository,
            "remote_name": settings.remote_name,
            "branch": branch,
            "development_branch": settings.development_branch,
            "production_branch": settings.production_branch,
            "local_changes": len(changes),
            "remote_changes": behind,
            "ahead": ahead,
            "behind": behind,
            "sync_state": "conflict" if ahead and behind else "changes" if changes or ahead or behind else "synced",
            "last_commit": commit,
            "last_publication": self._publication(root, settings),
        }

    def changes(self, project_id: str) -> dict:
        root = self._connected_root(project_id)
        changes = collect_changes(root, self.runner)
        return {
            "changes": changes,
            "suggested_message": self._suggested_message(changes),
        }

    def history(self, project_id: str, limit: int = 30) -> dict:
        root = self._connected_root(project_id)
        settings = self._settings(root)
        raw = self.runner.run(root, [
            "log", "--all", f"--max-count={max(1, min(limit, 100))}",
            "--date=iso-strict", "--format=%H%x1f%an%x1f%aI%x1f%s%x1e",
        ]).stdout
        production = self._revision(root, f"{settings.remote_name}/{settings.production_branch}")
        commits = []
        for record in raw.split("\x1e"):
            if not record.strip():
                continue
            fields = record.strip().split("\x1f", 3)
            if len(fields) != 4:
                continue
            commit_hash, author, authored_at, message = fields
            published = bool(production and self._is_ancestor(root, commit_hash, production))
            commits.append({
                "hash": commit_hash,
                "short_hash": commit_hash[:7],
                "author": author,
                "authored_at": authored_at,
                "message": message,
                "published": published,
                "branch": settings.production_branch if commit_hash == production else settings.development_branch,
                "url": f"https://github.com/{settings.repository}/commit/{commit_hash}",
            })
        return {"commits": commits}

    def fetch(self, project_id: str, token: str | None) -> dict:
        root = self._connected_root(project_id)
        settings = self._settings(root)
        self.runner.run(root, ["fetch", "--prune", settings.remote_name], token=token)
        return self.status(project_id)

    def connect(self, project_id: str, request: GitConnectRequest) -> dict:
        root = self._root(project_id)
        repository = self.github.repository(request.repository, request.token or "")
        clone_url = str(repository.get("clone_url") or f"https://github.com/{request.repository}.git")
        initialized = (root / ".git").exists()
        if not initialized:
            self.runner.run(root, ["init", "-b", request.development_branch])
        remotes = self.runner.run(root, ["remote"], check=False).stdout.split()
        if request.remote_name in remotes:
            existing = self.runner.run(root, ["remote", "get-url", request.remote_name]).stdout.strip()
            if self._repository_from_url(existing) != request.repository:
                raise IncompatibleHistory("The existing Git remote points to another repository.")
            self.runner.run(root, ["remote", "set-url", request.remote_name, clone_url])
        else:
            self.runner.run(root, ["remote", "add", request.remote_name, clone_url])
        self.runner.run(root, ["fetch", request.remote_name], token=request.token, check=False)
        remote_dev = self._revision(root, f"{request.remote_name}/{request.development_branch}")
        local_head = self._revision(root, "HEAD")
        if remote_dev and local_head and not (
            self._is_ancestor(root, local_head, remote_dev)
            or self._is_ancestor(root, remote_dev, local_head)
        ):
            raise IncompatibleHistory("The local project and GitHub repository have incompatible histories.")
        if remote_dev and not local_head:
            raise IncompatibleHistory(
                "This folder contains project files but the repository already has history. Clone it into a new folder, then open that folder in Studio."
            )
        settings = GitSettings(
            repository=request.repository,
            remote_name=request.remote_name,
            development_branch=request.development_branch,
            production_branch=request.production_branch,
        )
        self._write_settings(root, settings)
        ensure_gitignore(root)
        return self.status(project_id)

    def create_repository(self, project_id: str, request: GitCreateRepositoryRequest) -> dict:
        root = self._root(project_id)
        if (root / ".git").exists():
            existing_remotes = self.runner.run(root, ["remote"], check=False).stdout.split()
            if request.remote_name in existing_remotes:
                raise IncompatibleHistory(
                    f"The Git remote '{request.remote_name}' already exists. Disconnect it before creating a new repository."
                )
        account = self.github.account(request.token or "")
        created = self.github.create_repository(request.repository, request.visibility, request.token or "")
        owner = str((created.get("owner") or {}).get("login") or account.get("login") or "")
        full_name = str(created.get("full_name") or f"{owner}/{request.repository}")
        if not (root / ".git").exists():
            self.runner.run(root, ["init", "-b", request.development_branch])
        ensure_gitignore(root)
        self._write_settings(root, GitSettings(
            repository=full_name,
            remote_name=request.remote_name,
            development_branch=request.development_branch,
            production_branch=request.production_branch,
        ))
        clone_url = str(created.get("clone_url") or f"https://github.com/{full_name}.git")
        self.runner.run(root, ["remote", "add", request.remote_name, clone_url])
        self._ensure_author(root, account)
        changes = collect_changes(root, self.runner, include_diff=False)
        scan_for_secrets(root, self._committable_paths(root))
        self.runner.run(root, ["add", "--all"])
        if not self._revision(root, "HEAD"):
            self.runner.run(root, ["commit", "-m", "Initial bot project"])
        self.runner.run(root, ["push", "-u", request.remote_name, f"HEAD:{request.development_branch}"], token=request.token)
        head = self._revision(root, "HEAD")
        self.runner.run(root, ["push", request.remote_name, f"{head}:refs/heads/{request.production_branch}"], token=request.token)
        return self.status(project_id)

    def disconnect(self, project_id: str) -> dict:
        root = self._connected_root(project_id)
        settings = self._settings(root)
        self.runner.run(root, ["remote", "remove", settings.remote_name], check=False)
        self._settings_path(root).unlink(missing_ok=True)
        return {"connected": False, "git_installed": self._git_installed(root)}

    def sync(self, project_id: str, token: str | None) -> dict:
        root = self._connected_root(project_id)
        settings = self._settings(root)
        if collect_changes(root, self.runner, include_diff=False):
            raise WorkingTreeDirty("Local changes are not overwritten. Push or discard them before syncing.")
        if self._branch(root) != settings.development_branch:
            raise WorkingTreeDirty(f"Switch to the shared branch '{settings.development_branch}' before syncing.")
        self.runner.run(root, ["fetch", "--prune", settings.remote_name], token=token)
        remote = f"{settings.remote_name}/{settings.development_branch}"
        if self._revision(root, remote):
            self.runner.run(root, ["merge", "--ff-only", remote])
        return self.status(project_id)

    def push(self, project_id: str, request: GitPushRequest) -> dict:
        root = self._connected_root(project_id)
        settings = self._settings(root)
        if self._branch(root) != settings.development_branch:
            raise WorkingTreeDirty(f"Push is available from '{settings.development_branch}'.")
        self.runner.run(root, ["fetch", "--prune", settings.remote_name], token=request.token)
        _ahead, behind = self._ahead_behind(root, settings, settings.development_branch)
        if behind:
            raise RemoteChangesDetected("A newer project version is available. Sync before pushing.")
        issues = self.validate_project(project_id)
        errors = [issue for issue in issues if issue.get("level") == "error"]
        if errors:
            raise ValidationFailed("Project validation failed.", details={"issues": errors})
        ensure_gitignore(root)
        changes = collect_changes(root, self.runner, include_diff=False)
        if not changes:
            return {"pushed": False, "reason": "no_changes", "status": self.status(project_id)}
        scan_for_secrets(root, self._committable_paths(root))
        self.runner.run(root, ["add", "--all"])
        self._ensure_author(
            root,
            self.github.account(request.token or "") if request.token else None,
        )
        self.runner.run(root, ["commit", "-m", request.message.strip()])
        self.runner.run(root, ["push", settings.remote_name, f"HEAD:{settings.development_branch}"], token=request.token)
        commit = self._last_commit(root)
        return {"pushed": True, "commit": commit, "changed_files": len(changes), "status": self.status(project_id)}

    def publish(self, project_id: str, request: GitPublishRequest) -> dict:
        root = self._connected_root(project_id)
        settings = self._settings(root)
        if collect_changes(root, self.runner, include_diff=False):
            raise WorkingTreeDirty("Save and push local changes before publishing.")
        if self._branch(root) != settings.development_branch:
            raise WorkingTreeDirty(f"Publish is available from '{settings.development_branch}'.")
        self.runner.run(root, ["fetch", "--prune", settings.remote_name], token=request.token)
        _ahead, behind = self._ahead_behind(root, settings, settings.development_branch)
        if behind:
            raise RemoteChangesDetected("Sync the shared development branch before publishing.")
        errors = [issue for issue in self.validate_project(project_id) if issue.get("level") == "error"]
        if errors:
            raise ValidationFailed("Production publishing requires a valid project.", details={"issues": errors})
        development = self._revision(root, "HEAD")
        production_ref = f"{settings.remote_name}/{settings.production_branch}"
        production = self._revision(root, production_ref)
        if production and not self._is_ancestor(root, production, development):
            raise ProductionDiverged("Production contains changes that are not in development. Publishing was stopped.")
        test_result = self._run_project_tests(root)
        self.runner.run(
            root,
            ["push", settings.remote_name, f"{development}:refs/heads/{settings.production_branch}"],
            token=request.token,
        )
        version = self._next_version(root, request)
        if version:
            self.runner.run(root, ["tag", "-a", version, "-m", f"Release {version}"])
            self.runner.run(root, ["push", settings.remote_name, f"refs/tags/{version}"], token=request.token)
        now = datetime.now(UTC).isoformat()
        return {
            "published": True,
            "commit": development,
            "version": version,
            "published_at": now,
            "tests": test_result,
            "status": self.status(project_id),
        }

    def _root(self, project_id: str) -> Path:
        return self.repository.workspace(project_id).root

    def _connected_root(self, project_id: str) -> Path:
        root = self._root(project_id)
        if not (root / ".git").exists() or not self._settings_path(root).is_file():
            raise RepositoryNotConnected("Connect this project to GitHub first.")
        return root

    def _settings(self, root: Path) -> GitSettings:
        try:
            return GitSettings.model_validate_json(self._settings_path(root).read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise RepositoryNotConnected("Git settings are missing or invalid.") from error

    @staticmethod
    def _settings_path(root: Path) -> Path:
        return root / ".botstudio" / "git.json"

    def _write_settings(self, root: Path, settings: GitSettings) -> None:
        path = self._settings_path(root)
        WorkspaceRepository.atomic_write(
            path,
            (settings.model_dump_json(indent=2, exclude_none=True) + "\n").encode(),
        )

    def _git_installed(self, root: Path) -> bool:
        try:
            return self.runner.run(root, ["--version"], check=False).returncode == 0
        except GitNotInstalled:
            return False

    def _branch(self, root: Path) -> str:
        return self.runner.run(root, ["branch", "--show-current"], check=False).stdout.strip()

    def _last_commit(self, root: Path) -> dict | None:
        result = self.runner.run(
            root,
            ["log", "-1", "--date=iso-strict", "--format=%H%x1f%an%x1f%aI%x1f%s"],
            check=False,
        )
        fields = result.stdout.strip().split("\x1f", 3)
        if len(fields) != 4:
            return None
        return {"hash": fields[0], "short_hash": fields[0][:7], "author": fields[1], "authored_at": fields[2], "message": fields[3]}

    def _ahead_behind(self, root: Path, settings: GitSettings, branch: str) -> tuple[int, int]:
        remote = f"{settings.remote_name}/{settings.development_branch}"
        if not self._revision(root, "HEAD") or not self._revision(root, remote):
            return 0, 0
        value = self.runner.run(root, ["rev-list", "--left-right", "--count", f"HEAD...{remote}"], check=False).stdout.split()
        return (int(value[0]), int(value[1])) if len(value) == 2 else (0, 0)

    def _revision(self, root: Path, ref: str) -> str | None:
        result = self.runner.run(root, ["rev-parse", "--verify", ref], check=False)
        return result.stdout.strip() if result.returncode == 0 else None

    def _is_ancestor(self, root: Path, ancestor: str, descendant: str) -> bool:
        return self.runner.run(root, ["merge-base", "--is-ancestor", ancestor, descendant], check=False).returncode == 0

    def _publication(self, root: Path, settings: GitSettings) -> dict | None:
        production = self._revision(root, f"{settings.remote_name}/{settings.production_branch}")
        if not production:
            return None
        detail = self.runner.run(
            root,
            ["show", "-s", "--date=iso-strict", "--format=%H%x1f%aI", production],
            check=False,
        ).stdout.strip().split("\x1f", 1)
        tags = self.runner.run(
            root,
            ["tag", "--points-at", production, "--list", "v[0-9]*"],
            check=False,
        ).stdout.splitlines()
        return {
            "version": tags[0] if tags else None,
            "commit": production,
            "at": detail[1] if len(detail) == 2 else None,
        }

    def _committable_paths(self, root: Path) -> list[str]:
        raw = self.runner.run(
            root,
            ["ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        ).stdout
        return [path for path in raw.split("\0") if path]

    def _ensure_author(self, root: Path, account: dict | None) -> None:
        name = self.runner.run(root, ["config", "--get", "user.name"], check=False).stdout.strip()
        email = self.runner.run(root, ["config", "--get", "user.email"], check=False).stdout.strip()
        if name and email:
            return
        if not account:
            raise ValidationFailed(
                "Git author details are missing. Connect GitHub again or configure a Git name and email."
            )
        login = str(account.get("login") or "studio-user")
        if not name:
            self.runner.run(root, ["config", "user.name", str(account.get("name") or login)])
        if not email:
            account_email = account.get("email")
            account_id = account.get("id")
            fallback = f"{account_id}+{login}@users.noreply.github.com" if account_id else f"{login}@users.noreply.github.com"
            self.runner.run(root, ["config", "user.email", str(account_email or fallback)])

    @staticmethod
    def _repository_from_url(url: str) -> str:
        match = re.search(r"github\.com[/:]([^/]+/[^/]+?)(?:\.git)?$", url)
        return match.group(1) if match else url

    @staticmethod
    def _suggested_message(changes: list[dict]) -> str:
        if not changes:
            return ""
        groups: dict[str, int] = {}
        for change in changes:
            path = change["path"]
            group = "templates" if path.startswith("resources/templates/") else "views" if path.startswith("resources/views/") else "flows" if path.startswith("resources/flows/") else "files"
            groups[group] = groups.get(group, 0) + 1
        summary = ", ".join(f"{count} {name}" for name, count in groups.items())
        return f"Update {summary}"

    def _next_version(self, root: Path, request: GitPublishRequest) -> str | None:
        if request.version == "none":
            return None
        if request.version == "custom":
            assert request.custom_version
            return request.custom_version if request.custom_version.startswith("v") else f"v{request.custom_version}"
        tags = self.runner.run(root, ["tag", "--list", "v[0-9]*.[0-9]*.[0-9]*", "--sort=-v:refname"], check=False).stdout.splitlines()
        match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", tags[0]) if tags else None
        major, minor, patch = (map(int, match.groups()) if match else (0, 0, 0))
        if request.version == "major":
            major, minor, patch = major + 1, 0, 0
        elif request.version == "minor":
            minor, patch = minor + 1, 0
        else:
            patch += 1
        return f"v{major}.{minor}.{patch}"

    @staticmethod
    def _run_project_tests(root: Path) -> dict:
        if not (root / "tests").is_dir():
            return {"available": False, "passed": None}
        candidates = (
            root / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python"),
        )
        python = next((candidate for candidate in candidates if candidate.is_file()), None)
        if not python:
            return {"available": True, "passed": None, "message": "Project environment is not prepared."}
        import subprocess
        try:
            result = subprocess.run([str(python), "-m", "pytest", "-q"], cwd=root, shell=False, capture_output=True, timeout=180)
        except subprocess.TimeoutExpired:
            return {"available": True, "passed": False, "message": "Project tests timed out."}
        if result.returncode:
            raise ValidationFailed("Project tests failed.", details={"test_summary": result.stdout.decode("utf-8", errors="replace")[-4000:]})
        return {"available": True, "passed": True}
