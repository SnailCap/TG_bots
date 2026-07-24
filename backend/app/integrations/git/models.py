from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


_BRANCH_PATTERN = r"^[A-Za-z0-9._/-]{1,128}$"
_REPOSITORY_PATTERN = r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$"


class GitCredentials(BaseModel):
    token: str | None = Field(default=None, max_length=4096, repr=False)


class GitConnectRequest(GitCredentials):
    repository: str = Field(pattern=_REPOSITORY_PATTERN)
    remote_name: str = Field(default="origin", pattern=r"^[A-Za-z0-9._-]{1,64}$")
    development_branch: str = Field(default="dev", pattern=_BRANCH_PATTERN)
    production_branch: str = Field(default="production", pattern=_BRANCH_PATTERN)

    @field_validator("development_branch", "production_branch")
    @classmethod
    def branch_name_is_safe(cls, value: str):
        if (
            value[0] in "-/."
            or value[-1] in "/."
            or ".." in value
            or "//" in value
            or "@{" in value
            or "\\" in value
        ):
            raise ValueError("Invalid Git branch name.")
        return value

    @field_validator("production_branch")
    @classmethod
    def branches_must_differ(cls, value: str, info):
        if value == info.data.get("development_branch"):
            raise ValueError("Production branch must differ from development branch.")
        return value


class GitCreateRepositoryRequest(GitConnectRequest):
    repository: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,100}$")
    visibility: Literal["private", "public"] = "private"


class GitOperationRequest(GitCredentials):
    pass


class GitPushRequest(GitCredentials):
    message: str = Field(min_length=1, max_length=240)


class GitPublishRequest(GitCredentials):
    version: Literal["patch", "minor", "major", "none", "custom"] = "none"
    custom_version: str | None = Field(default=None, pattern=r"^v?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")

    @field_validator("custom_version")
    @classmethod
    def custom_version_is_present(cls, value: str | None, info):
        if info.data.get("version") == "custom" and not value:
            raise ValueError("A custom version is required.")
        return value


class GitSettings(BaseModel):
    repository: str
    remote_name: str = "origin"
    development_branch: str = "dev"
    production_branch: str = "production"
    last_published_version: str | None = None
    last_published_commit: str | None = None
    last_published_at: str | None = None
