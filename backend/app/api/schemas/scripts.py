from __future__ import annotations

from app.domain.scripting import ScriptAction
from app.domain.validation import ValidationIssue

from .common import ApiModel


class ScriptPathResponse(ApiModel):
    path: str


class ScriptContentResponse(ApiModel):
    path: str
    name: str
    content: str


class CreateScriptRequest(ApiModel):
    path: str
    content: str = ""


class SaveScriptRequest(ApiModel):
    path: str
    content: str


class RenameFileRequest(ApiModel):
    path: str
    new_path: str


class ValidateScriptRequest(ApiModel):
    content: str
    path: str | None = None


class SearchMatchResponse(ApiModel):
    path: str
    line: int
    column: int
    preview: str


class ActionParameterResponse(ApiModel):
    name: str
    annotation: str | None
    required: bool


class ScriptActionResponse(ApiModel):
    name: str
    module: str
    file_path: str
    line: int
    is_async: bool
    parameters: list[ActionParameterResponse]
    docstring: str | None


class ActionUsageResponse(ApiModel):
    action_name: str
    flow_id: str
    flow_name: str
    node_id: str
    node_name: str


class ValidationIssueResponse(ApiModel):
    severity: str
    code: str
    message: str
    entity_type: str | None
    entity_id: str | None
    path: str | None
    hint: str | None


class ActionsResponse(ApiModel):
    actions: list[ScriptActionResponse]
    issues: list[ValidationIssueResponse]
    valid: bool


def action_response(value: ScriptAction) -> ScriptActionResponse:
    return ScriptActionResponse(
        name=value.name,
        module=value.module,
        file_path=value.file_path,
        line=value.line,
        is_async=value.is_async,
        parameters=[
            ActionParameterResponse(
                name=item.name,
                annotation=item.annotation,
                required=item.required,
            )
            for item in value.parameters
        ],
        docstring=value.docstring,
    )


def issue_response(value: ValidationIssue) -> ValidationIssueResponse:
    return ValidationIssueResponse(
        severity=value.severity.value,
        code=value.code,
        message=value.message,
        entity_type=value.entity_type,
        entity_id=value.entity_id,
        path=value.path,
        hint=value.hint,
    )
