from __future__ import annotations

import httpx

from .errors import AuthenticationRequired, GitIntegrationError, NetworkUnavailable


class GitHubClient:
    def __init__(
        self,
        base_url: str = "https://api.github.com",
        timeout: float = 20.0,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport

    def account(self, token: str) -> dict:
        return self._request("GET", "/user", token=token)

    def repository(self, repository: str, token: str) -> dict:
        return self._request("GET", f"/repos/{repository}", token=token)

    def create_repository(self, name: str, visibility: str, token: str) -> dict:
        return self._request(
            "POST",
            "/user/repos",
            token=token,
            json={"name": name, "private": visibility == "private", "auto_init": False},
        )

    def _request(self, method: str, path: str, *, token: str, json: dict | None = None) -> dict:
        if not token:
            raise AuthenticationRequired("Connect a GitHub account to continue.")
        try:
            with httpx.Client(transport=self.transport, timeout=self.timeout) as client:
                response = client.request(
                    method,
                    f"{self.base_url}{path}",
                    headers={
                        "Accept": "application/vnd.github+json",
                        "Authorization": f"Bearer {token}",
                        "X-GitHub-Api-Version": "2022-11-28",
                        "User-Agent": "Telegram-Bot-Studio",
                    },
                    json=json,
                )
        except httpx.RequestError as error:
            raise NetworkUnavailable("GitHub could not be reached. Check the network connection.") from error
        if response.status_code in (401, 403):
            raise AuthenticationRequired("GitHub rejected the saved credentials.")
        if response.status_code >= 400:
            raise GitIntegrationError(
                "GitHub could not complete the request.",
                details={"github_status": response.status_code},
            )
        value = response.json()
        if not isinstance(value, dict):
            raise GitIntegrationError("GitHub returned an unexpected response.")
        return value
