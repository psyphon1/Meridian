from typing import Any, cast

import httpx

from packages.github.errors import (
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
)
from packages.github.token_cache import InstallationTokenCache

GITHUB_API = "https://api.github.com"


class GitHubClient:
    """Typed async GitHub API client with rate-limit awareness."""

    def __init__(
        self,
        token_cache: InstallationTokenCache | None,
        private_key: str = "",
        app_id: int = 0,
    ) -> None:
        self._token_cache = token_cache
        self._private_key = private_key
        self._app_id = app_id

    def _base_url(self) -> str:
        return GITHUB_API

    def _check_response(self, resp: httpx.Response) -> None:
        if resp.status_code == 401:
            raise AuthenticationError(str(resp.text), 401)
        if resp.status_code == 404:
            raise NotFoundError(str(resp.text), 404)
        if resp.status_code == 422:
            raise ValidationError(str(resp.text), 422)
        if resp.status_code in (429, 403):
            retry = int(resp.headers.get("Retry-After", "60"))
            raise RateLimitError(str(resp.text), retry_after=retry)
        if resp.status_code >= 500:
            raise ServerError(str(resp.text), resp.status_code)

    async def get_pr_files(self, owner: str, repo: str, pr_number: int) -> list[dict[str, Any]]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base_url()}/repos/{owner}/{repo}/pulls/{pr_number}/files",
                headers={"Accept": "application/vnd.github+json"},
            )
            self._check_response(resp)
            return cast(list[dict[str, Any]], resp.json())

    async def get_pr_diff(self, owner: str, repo: str, pr_number: int) -> str:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base_url()}/repos/{owner}/{repo}/pulls/{pr_number}",
                headers={"Accept": "application/vnd.github.v3.diff"},
            )
            self._check_response(resp)
            return resp.text

    async def post_review(
        self, owner: str, repo: str, pr_number: int, review: dict[str, Any]
    ) -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url()}/repos/{owner}/{repo}/pulls/{pr_number}/reviews",
                json=review,
                headers={"Accept": "application/vnd.github+json"},
            )
            self._check_response(resp)

    async def post_comment(self, owner: str, repo: str, pr_number: int, body: str) -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url()}/repos/{owner}/{repo}/issues/{pr_number}/comments",
                json={"body": body},
                headers={"Accept": "application/vnd.github+json"},
            )
            self._check_response(resp)
