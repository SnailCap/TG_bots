from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import httpx

from app.integrations.git.command_runner import CommandResult, GitCommandRunner
from app.integrations.git.errors import (
    AuthenticationRequired,
    GitCommandTimeout,
    GitNotInstalled,
    NetworkUnavailable,
    ProductionDiverged,
    RemoteChangesDetected,
    SecretDetected,
    WorkingTreeDirty,
)
from app.integrations.git.models import (
    GitConnectRequest,
    GitCreateRepositoryRequest,
    GitOperationRequest,
    GitPublishRequest,
    GitPushRequest,
)
from app.integrations.git.github_client import GitHubClient
from app.integrations.git.service import GitService
from app.integrations.git.status import parse_porcelain, semantic_summary
from app.workspace import ProjectService


class LocalGitHub:
    def __init__(self, bare: Path) -> None:
        self.bare = bare

    def repository(self, repository: str, token: str) -> dict:
        return {"full_name": repository, "clone_url": str(self.bare)}

    def account(self, token: str) -> dict:
        return {"id": 42, "login": "studio-user", "name": "Studio User"}

    def create_repository(self, name: str, visibility: str, token: str) -> dict:
        return {
            "full_name": f"studio-user/{name}",
            "clone_url": str(self.bare),
            "owner": {"login": "studio-user"},
            "private": visibility == "private",
        }


def git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=check,
    )


@pytest.fixture()
def connected(tmp_path: Path) -> tuple[GitService, str, Path, Path]:
    project_service = ProjectService()
    workspace = project_service.create_starter(parent_path=str(tmp_path), name="Shared Bot")
    project_id = workspace["project_id"]
    root = Path(workspace["project_root"])
    bare = tmp_path / "shared.git"
    git(tmp_path, "init", "--bare", str(bare))
    service = GitService(
        project_service.repository,
        project_service.validate,
        github=LocalGitHub(bare),  # type: ignore[arg-type]
    )
    service.connect(
        project_id,
        GitConnectRequest(
            repository="studio/shared-bot",
            development_branch="dev",
            production_branch="production",
        ),
    )
    git(root, "config", "user.name", "Studio Test")
    git(root, "config", "user.email", "studio@example.test")
    service.push(project_id, GitPushRequest(message="Initial project"))
    return service, project_id, root, bare


def collaborator(tmp_path: Path, bare: Path, branch: str = "dev") -> Path:
    clone = tmp_path / f"collaborator-{branch}"
    git(tmp_path, "clone", str(bare), str(clone))
    git(clone, "config", "user.name", "Collaborator")
    git(clone, "config", "user.email", "collaborator@example.test")
    git(clone, "checkout", branch)
    return clone


def test_disconnected_status_and_safe_connection(connected) -> None:
    service, project_id, root, _bare = connected
    status = service.status(project_id)
    assert status["connected"] is True
    assert status["repository"] == "studio/shared-bot"
    assert status["branch"] == "dev"
    assert status["sync_state"] == "synced"
    settings = json.loads((root / ".botstudio" / "git.json").read_text(encoding="utf-8"))
    assert settings["development_branch"] == "dev"
    assert "token" not in settings


def test_existing_git_folder_without_studio_settings_is_setup_state(tmp_path: Path) -> None:
    projects = ProjectService()
    workspace = projects.create_starter(parent_path=str(tmp_path), name="Existing Git Bot")
    root = Path(workspace["project_root"])
    git(root, "init", "-b", "dev")
    status = GitService(projects.repository, projects.validate).status(workspace["project_id"])
    assert status == {"connected": False, "git_installed": True, "repository_detected": True}


def test_create_repository_initializes_and_pushes_both_branches(tmp_path: Path) -> None:
    projects = ProjectService()
    workspace = projects.create_starter(parent_path=str(tmp_path), name="Created Repository Bot")
    bare = tmp_path / "created.git"
    git(tmp_path, "init", "--bare", str(bare))
    service = GitService(
        projects.repository,
        projects.validate,
        github=LocalGitHub(bare),  # type: ignore[arg-type]
    )
    status = service.create_repository(
        workspace["project_id"],
        GitCreateRepositoryRequest(
            repository="created-repository-bot",
            visibility="private",
            token="secure-token",
            development_branch="dev",
            production_branch="production",
        ),
    )
    assert status["repository"] == "studio-user/created-repository-bot"
    assert git(bare, "rev-parse", "dev").returncode == 0
    assert git(bare, "rev-parse", "production").returncode == 0


def test_status_parser_supports_renames_and_untracked_files() -> None:
    parsed = parse_porcelain("R  new.txt\0old.txt\0?? fresh.txt\0 M changed.txt\0")
    assert parsed == [
        {"path": "old.txt", "old_path": "new.txt", "status": "renamed", "staged": True},
        {"path": "fresh.txt", "old_path": None, "status": "untracked", "staged": False},
        {"path": "changed.txt", "old_path": None, "status": "modified", "staged": False},
    ]


def test_internal_view_text_changes_are_presented_as_view_edits() -> None:
    change = {
        "path": "resources/templates/views/welcome.txt",
        "status": "modified",
    }
    assert semantic_summary(change) == "View text “welcome” updated"
    assert GitService._suggested_message([change]) == "Update 1 view texts"


def test_sync_fast_forwards_clean_project(connected, tmp_path: Path) -> None:
    service, project_id, root, bare = connected
    other = collaborator(tmp_path, bare)
    (other / "README.md").write_text("# Changed by collaborator\n", encoding="utf-8")
    git(other, "add", "README.md")
    git(other, "commit", "-m", "Remote change")
    git(other, "push", "origin", "dev")

    fetched = service.fetch(project_id, None)
    assert fetched["behind"] == 1
    synced = service.sync(project_id, None)
    assert synced["behind"] == 0
    assert (root / "README.md").read_text(encoding="utf-8") == "# Changed by collaborator\n"


def test_sync_never_overwrites_local_changes(connected, tmp_path: Path) -> None:
    service, project_id, root, _bare = connected
    (root / "README.md").write_text("local draft\n", encoding="utf-8")
    with pytest.raises(WorkingTreeDirty):
        service.sync(project_id, None)
    assert (root / "README.md").read_text(encoding="utf-8") == "local draft\n"


def test_push_rechecks_remote_and_is_rejected_when_behind(connected, tmp_path: Path) -> None:
    service, project_id, root, bare = connected
    other = collaborator(tmp_path, bare)
    (other / "README.md").write_text("remote\n", encoding="utf-8")
    git(other, "add", "README.md")
    git(other, "commit", "-m", "Remote change")
    git(other, "push", "origin", "dev")
    (root / "resources" / "templates" / "views" / "home.txt").write_text("Local\n", encoding="utf-8")
    with pytest.raises(RemoteChangesDetected):
        service.push(project_id, GitPushRequest(message="Local change"))


def test_push_blocks_secrets_and_keeps_them_uncommitted(connected) -> None:
    service, project_id, root, _bare = connected
    secret = root / "src" / "shared_bot" / "config.py"
    secret.write_text('TOKEN = "123456789:abcdefghijklmnopqrstuvwxyzABCDEFGHIJK"\n', encoding="utf-8")
    with pytest.raises(SecretDetected) as caught:
        service.push(project_id, GitPushRequest(message="Unsafe change"))
    assert caught.value.details == {"files": ["src/shared_bot/config.py"]}
    assert "123456789:" not in str(caught.value.details)
    assert git(root, "status", "--porcelain").stdout


def test_successful_push_and_history(connected) -> None:
    service, project_id, root, _bare = connected
    (root / "resources" / "templates" / "views" / "home.txt").write_text("Welcome team!\n", encoding="utf-8")
    result = service.push(project_id, GitPushRequest(message="Update welcome text"))
    assert result["pushed"] is True
    assert result["commit"]["message"] == "Update welcome text"
    changes = service.changes(project_id)
    assert changes["changes"] == []
    assert service.history(project_id)["commits"][0]["message"] == "Update welcome text"


def test_publish_fast_forwards_production_and_creates_tag(connected) -> None:
    service, project_id, root, bare = connected
    (root / "resources" / "templates" / "views" / "home.txt").write_text("Release\n", encoding="utf-8")
    service.push(project_id, GitPushRequest(message="Prepare release"))
    result = service.publish(project_id, GitPublishRequest(version="patch"))
    assert result["version"] == "v0.0.1"
    assert git(bare, "rev-parse", "production").stdout.strip() == git(root, "rev-parse", "HEAD").stdout.strip()
    assert git(bare, "rev-parse", "refs/tags/v0.0.1").returncode == 0
    assert service.status(project_id)["local_changes"] == 0
    assert service.status(project_id)["last_publication"]["version"] == "v0.0.1"


def test_publish_stops_when_production_diverged(connected, tmp_path: Path) -> None:
    service, project_id, root, bare = connected
    service.publish(project_id, GitPublishRequest(version="none"))
    production = collaborator(tmp_path, bare, "production")
    (production / "production-note.txt").write_text("hotfix\n", encoding="utf-8")
    git(production, "add", "production-note.txt")
    git(production, "commit", "-m", "Production-only hotfix")
    git(production, "push", "origin", "production")
    (root / "resources" / "templates" / "views" / "home.txt").write_text("Next release\n", encoding="utf-8")
    service.push(project_id, GitPushRequest(message="Next development"))
    with pytest.raises(ProductionDiverged):
        service.publish(project_id, GitPublishRequest(version="none"))


def test_starter_gitignore_covers_runtime_and_local_artifacts(tmp_path: Path) -> None:
    workspace = ProjectService().create_starter(parent_path=str(tmp_path), name="Ignored Bot")
    ignored = set((Path(workspace["project_root"]) / ".gitignore").read_text(encoding="utf-8").splitlines())
    assert {"data/*.sqlite3", "data/*.sqlite3-wal", ".env", ".venv/", ".botstudio/backups/", ".botstudio/*.credentials*"} <= ignored


def test_command_runner_reports_missing_git(tmp_path: Path) -> None:
    with pytest.raises(GitNotInstalled):
        GitCommandRunner(executable="definitely-missing-git").run(tmp_path, ["--version"])


def test_disconnected_status_reports_missing_git_without_generic_error(tmp_path: Path) -> None:
    projects = ProjectService()
    workspace = projects.create_starter(parent_path=str(tmp_path), name="No Git Bot")
    service = GitService(
        projects.repository,
        projects.validate,
        runner=GitCommandRunner(executable="definitely-missing-git"),
    )
    assert service.status(workspace["project_id"]) == {
        "connected": False,
        "git_installed": False,
        "repository_detected": False,
    }


def test_command_runner_reports_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 0.01)

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(GitCommandTimeout):
        GitCommandRunner(timeout=0.01).run(tmp_path, ["status"])


def test_command_runner_maps_authentication_and_network_failures() -> None:
    with pytest.raises(AuthenticationRequired):
        GitCommandRunner._raise_failure(CommandResult("", "Authentication failed", 128))
    with pytest.raises(NetworkUnavailable):
        GitCommandRunner._raise_failure(CommandResult("", "Could not resolve host: github.com", 128))


def test_github_client_uses_mock_transport_without_real_account() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer secure-token"
        return httpx.Response(200, json={"login": "studio-user"})

    client = GitHubClient(transport=httpx.MockTransport(respond))
    assert client.account("secure-token")["login"] == "studio-user"
