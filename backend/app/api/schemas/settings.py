from pydantic import Field, SecretStr

from .common import ApiModel
from .projects import BotIdentityResponse


class PatchSettingsRequest(ApiModel):
    start_flow_id: str | None = None
    start_behavior: str | None = Field(default=None, pattern="^(reset|resume)$")


class SetTokenRequest(ApiModel):
    token: SecretStr


class TokenValidationResponse(ApiModel):
    valid: bool
    identity: BotIdentityResponse | None = None
    error: str | None = None
