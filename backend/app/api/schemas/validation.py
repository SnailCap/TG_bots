from .common import ApiModel
from .scripts import ValidationIssueResponse


class ValidationResponse(ApiModel):
    valid: bool
    issues: list[ValidationIssueResponse]

