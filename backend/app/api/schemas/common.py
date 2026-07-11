from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class HealthResponse(ApiModel):
    status: str
    schema_version: int
    api_version: str


class ErrorBody(ApiModel):
    code: str
    message: str
    details: dict = Field(default_factory=dict)


class ErrorResponse(ApiModel):
    error: ErrorBody
