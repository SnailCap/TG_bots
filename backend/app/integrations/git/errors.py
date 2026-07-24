from __future__ import annotations


class GitIntegrationError(RuntimeError):
    code = "git_error"
    status_code = 400

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.details = details


class GitNotInstalled(GitIntegrationError):
    code = "git_not_installed"
    status_code = 503


class RepositoryNotConnected(GitIntegrationError):
    code = "repository_not_connected"
    status_code = 409


class AuthenticationRequired(GitIntegrationError):
    code = "authentication_required"
    status_code = 401


class WorkingTreeDirty(GitIntegrationError):
    code = "working_tree_dirty"
    status_code = 409


class RemoteChangesDetected(GitIntegrationError):
    code = "remote_changes_detected"
    status_code = 409


class MergeConflict(GitIntegrationError):
    code = "merge_conflict"
    status_code = 409


class ValidationFailed(GitIntegrationError):
    code = "validation_failed"
    status_code = 422


class PushRejected(GitIntegrationError):
    code = "push_rejected"
    status_code = 409


class ProductionDiverged(GitIntegrationError):
    code = "production_diverged"
    status_code = 409


class SecretDetected(GitIntegrationError):
    code = "secret_detected"
    status_code = 422


class NetworkUnavailable(GitIntegrationError):
    code = "network_unavailable"
    status_code = 503


class GitCommandTimeout(GitIntegrationError):
    code = "git_timeout"
    status_code = 504


class IncompatibleHistory(GitIntegrationError):
    code = "incompatible_history"
    status_code = 409

