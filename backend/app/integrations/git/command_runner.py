from __future__ import annotations

import base64
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .errors import (
    AuthenticationRequired,
    GitCommandTimeout,
    GitIntegrationError,
    GitNotInstalled,
    MergeConflict,
    NetworkUnavailable,
    PushRejected,
)


@dataclass(frozen=True, slots=True)
class CommandResult:
    stdout: str
    stderr: str
    returncode: int


class GitCommandRunner:
    """Run a fixed git executable without a shell or credential-bearing arguments."""

    def __init__(self, executable: str = "git", timeout: float = 45.0) -> None:
        self.executable = executable
        self.timeout = timeout

    def run(
        self,
        root: Path,
        arguments: Sequence[str],
        *,
        token: str | None = None,
        check: bool = True,
        timeout: float | None = None,
    ) -> CommandResult:
        if not arguments or any("\x00" in argument for argument in arguments):
            raise GitIntegrationError("Invalid Git command arguments.")
        environment = {
            **os.environ,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
            "LC_ALL": "C.UTF-8",
        }
        if token:
            encoded = base64.b64encode(f"x-access-token:{token}".encode()).decode()
            environment.update({
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "http.extraHeader",
                "GIT_CONFIG_VALUE_0": f"Authorization: Basic {encoded}",
            })
        try:
            completed = subprocess.run(
                [self.executable, *arguments],
                cwd=root,
                env=environment,
                shell=False,
                capture_output=True,
                timeout=timeout or self.timeout,
                check=False,
            )
        except FileNotFoundError as error:
            raise GitNotInstalled(
                "Git is not installed or is not available on PATH."
            ) from error
        except subprocess.TimeoutExpired as error:
            raise GitCommandTimeout("The Git operation took too long and was stopped.") from error

        result = CommandResult(
            completed.stdout.decode("utf-8", errors="replace"),
            completed.stderr.decode("utf-8", errors="replace"),
            completed.returncode,
        )
        if check and result.returncode:
            self._raise_failure(result)
        return result

    @staticmethod
    def _raise_failure(result: CommandResult) -> None:
        diagnostic = f"{result.stderr}\n{result.stdout}".lower()
        if any(value in diagnostic for value in ("authentication failed", "could not read username", "permission denied", "403")):
            raise AuthenticationRequired("GitHub authentication is required.")
        if any(value in diagnostic for value in ("could not resolve host", "failed to connect", "connection timed out", "network is unreachable")):
            raise NetworkUnavailable("GitHub could not be reached. Check the network connection.")
        if "non-fast-forward" in diagnostic or "[rejected]" in diagnostic:
            raise PushRejected("GitHub has newer changes. Sync before pushing again.")
        if "conflict" in diagnostic:
            raise MergeConflict("Git could not combine the local and remote changes safely.")
        raise GitIntegrationError("Git could not complete the operation.")

