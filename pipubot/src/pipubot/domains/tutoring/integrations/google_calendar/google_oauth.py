from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class AccessToken:
    token: str


class AccessTokenProvider(Protocol):
    async def get_access_token(self) -> AccessToken:
        """
        Return a valid Bearer token.
        Later: implement refresh_token flow and caching here.
        """
        ...