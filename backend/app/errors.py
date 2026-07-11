from __future__ import annotations

from typing import Any


class StudioError(Exception):
    code = "studio_error"
    status_code = 400

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class UnsafePathError(StudioError):
    code = "unsafe_path"


class ProjectNotFoundError(StudioError):
    code = "project_not_found"
    status_code = 404


class ProjectAlreadyExistsError(StudioError):
    code = "project_already_exists"
    status_code = 409


class ProjectFormatError(StudioError):
    code = "invalid_project_format"
    status_code = 422


class UnsupportedSchemaVersionError(ProjectFormatError):
    code = "unsupported_schema_version"


class FlowNotFoundError(StudioError):
    code = "flow_not_found"
    status_code = 404


class ScriptNotFoundError(StudioError):
    code = "script_not_found"
    status_code = 404


class AssetNotFoundError(StudioError):
    code = "asset_not_found"
    status_code = 404


class ConflictError(StudioError):
    code = "conflict"
    status_code = 409


class SecretStoreError(StudioError):
    code = "secret_store_error"
    status_code = 503


class TokenValidationError(StudioError):
    code = "token_validation_failed"
    status_code = 422


class CapabilityUnavailableError(StudioError):
    code = "capability_unavailable"
    status_code = 501


class ValidationFailedError(StudioError):
    code = "validation_failed"
    status_code = 422


class RuntimeOperationError(StudioError):
    code = "runtime_operation_failed"
    status_code = 503
