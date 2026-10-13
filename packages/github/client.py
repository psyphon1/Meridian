"""Typed async GitHub REST client (spec §6.4, ADR-006 D5).

* Auth: installation token from :class:`InstallationTokenCache` for repo-scoped
  calls; a freshly minted App JWT for app-level calls (token exchange).
* 401 on an installation call → invalidate the cached token, fetch a new one,
  retry once.
* 429 / 403-with-rate-limit-signal → honour ``Retry-After`` (seconds or
  HTTP-date) / ``x-ratelimit-reset``; retried with exponential backoff + full
  jitter, at most ``max_retries`` times. A plain 403 is an
  :class:`AuthorizationError`, not a rate limit.
* 5xx / network errors → retried (idempotent GETs only, so a POST review is
  never duplicated), then surfaced as typed errors.
"""

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
import structlog
from pydantic import TypeAdapter
from pydantic import ValidationError as PydanticValidationError

from packages.github.auth import generate_app_jwt
from packages.github.errors import (
    AuthenticationError,
    AuthorizationError,
    GitHubError,
    NotFoundError,
    RateLimitError,
    ServerError,
    TransportError,
    ValidationError,
)
from packages.github.token_cache import InstallationTokenCache
from packages.github.types import InstallationToken, PRFile, ReviewPayload

GITHUB_API = "https://api.github.com"
_ACCEPT_JSON = "application/vnd.github+json"
_ACCEPT_DIFF = "application/vnd.github.v3.diff"
_API_VERSION = "2022-11-28"
_FILES_PER_PAGE = 100
_FILES_MAX_PAGES = 30  # GitHub caps a PR at 3000 files

_log = structlog.get_logger("github.client")
_PRFILES = TypeAdapter(list[PRFile])


def parse_retry_after(value: str | None, now: datetime | None = None) -> int | None:
    """Parse a ``Retry-After`` header (delta-seconds or HTTP-date) into whole seconds."""
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return int(value)
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    delta = (when - (now or datetime.now(UTC))).total_seconds()
    return max(0, int(delta + 0.999))  # round up so we never retry too early


def _rate_limit_delay(headers: httpx.Headers, now: float) -> int | None:
    """Seconds to wait per GitHub's headers, or ``None`` if there is no explicit signal."""
    retry_after = parse_retry_after(headers.get("retry-after"))
    if retry_after is not None:
        return retry_after
    if headers.get("x-ratelimit-remaining") == "0":
        reset = headers.get("x-ratelimit-reset", "")
        if reset.isdigit():
            return max(0, int(reset) - int(now))
        return 60
    return None


class GitHubClient:
    """Typed async GitHub API client with rate-limit awareness."""

    def __init__(
        self,
        token_cache: InstallationTokenCache | None,
        private_key: str = "",
        app_id: int = 0,
        *,
        http_client: httpx.AsyncClient | None = None,
        base_url: str = GITHUB_API,
        max_retries: int = 3,
        backoff_base_s: float = 1.0,
        backoff_cap_s: float = 30.0,
        max_retry_after_s: float = 60.0,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        jitter: Callable[[float], float] = lambda cap: random.uniform(0, cap),  # noqa: S311
    ) -> None:
        self._private_key = private_key
        self._app_id = app_id
        self._http = http_client
        self._owns_http = http_client is None
        self._base = base_url.rstrip("/")
        self._max_retries = max_retries
        self._backoff_base = backoff_base_s
        self._backoff_cap = backoff_cap_s
        self._max_retry_after = max_retry_after_s
        self._sleep = sleep
        self._jitter = jitter
        # No cache supplied → L1-only cache so installation calls still work.
        self._token_cache = token_cache or InstallationTokenCache(None)
        if not self._token_cache.has_fetcher:
            self._token_cache.set_fetcher(self._fetch_installation_token)

    # -- lifecycle ---------------------------------------------------------

    def _base_url(self) -> str:
        return self._base

    def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0))
        return self._http

    async def aclose(self) -> None:
        """Close the underlying HTTP client if this instance created it."""
        if self._http is not None and self._owns_http:
            await self._http.aclose()
            self._http = None

    # -- auth --------------------------------------------------------------

    async def get_installation_token(self, installation_id: int) -> str:
        """Installation access token via the L1/L2 cache (fetching on a miss)."""
        return await self._token_cache.get_token(installation_id)

    async def _fetch_installation_token(self, installation_id: int) -> tuple[str, float]:
        """Cache fetch callback: ``POST /app/installations/{id}/access_tokens`` (App JWT)."""
        resp = await self._send(
            "POST",
            f"/app/installations/{installation_id}/access_tokens",
            installation_id=None,
            accept=_ACCEPT_JSON,
            retry_safe=True,  # minting a token has no side effect worth protecting
        )
        try:
            parsed = InstallationToken.model_validate_json(resp.content)
        except PydanticValidationError as exc:
            raise GitHubError("unexpected installation token response", resp.status_code) from exc
        return parsed.token, parsed.expires_at.timestamp()

    async def _auth_header(self, installation_id: int | None) -> str:
        if installation_id is None:
            return f"Bearer {generate_app_jwt(self._private_key, self._app_id)}"
        return f"token {await self.get_installation_token(installation_id)}"

    # -- transport ---------------------------------------------------------

    def _backoff(self, attempt: int) -> float:
        return float(self._jitter(min(self._backoff_cap, self._backoff_base * 2**attempt)))

    async def _send(
        self,
        method: str,
        path: str,
        *,
        installation_id: int | None,
        accept: str = _ACCEPT_JSON,
        json_body: Any = None,
        params: dict[str, Any] | None = None,
        retry_safe: bool = False,
    ) -> httpx.Response:
        """Authenticated request with 401-refresh, rate-limit and 5xx retry handling."""
        attempt = 0
        refreshed = False
        idempotent = retry_safe or method in {"GET", "HEAD"}
        while True:
            headers = {
                "Accept": accept,
                "X-GitHub-Api-Version": _API_VERSION,
                "Authorization": await self._auth_header(installation_id),
            }
            try:
                resp = await self._client().request(
                    method,
                    f"{self._base}{path}",
                    headers=headers,
                    json=json_body,
                    params=params,
                )
            except httpx.TransportError as exc:
                if idempotent and attempt < self._max_retries:
                    await self._sleep(self._backoff(attempt))
                    attempt += 1
                    continue
                raise TransportError(f"{method} {path}: {type(exc).__name__}") from exc

            status = resp.status_code
            if status < 400:
                return resp

            if status == 401:
                if installation_id is not None and not refreshed:
                    _log.warning("github.auth_401", path=path, installation_id=installation_id)
                    await self._token_cache.invalidate(installation_id)
                    refreshed = True
                    continue
                _log.error("github.auth_401_final", path=path)
                raise AuthenticationError(self._msg(resp), 401)

            if status == 429 or status == 403:
                delay = _rate_limit_delay(resp.headers, time.time())
                if status == 429 and delay is None:
                    delay = 60
                if delay is not None:
                    _log.warning(
                        "github.rate_limited",
                        path=path,
                        status=status,
                        retry_after=delay,
                        attempt=attempt,
                        remaining=resp.headers.get("x-ratelimit-remaining"),
                    )
                    if attempt < self._max_retries and delay <= self._max_retry_after:
                        # Honour GitHub's wait; add backoff jitter to avoid herd retries.
                        await self._sleep(max(delay, self._backoff(attempt)))
                        attempt += 1
                        continue
                    raise RateLimitError(self._msg(resp), retry_after=delay)
                raise AuthorizationError(self._msg(resp), 403)

            if status >= 500:
                if idempotent and attempt < self._max_retries:
                    _log.warning("github.server_error", path=path, status=status, attempt=attempt)
                    await self._sleep(self._backoff(attempt))
                    attempt += 1
                    continue
                raise ServerError(self._msg(resp), status)

            if status == 404:
                raise NotFoundError(self._msg(resp), 404)
            if status == 422:
                raise ValidationError(self._msg(resp), 422)
            raise GitHubError(self._msg(resp), status)

    @staticmethod
    def _msg(resp: httpx.Response) -> str:
        return resp.text[:500]

    # -- API methods -------------------------------------------------------

    async def get_pr_files(
        self, owner: str, repo: str, pr_number: int, *, installation_id: int
    ) -> list[PRFile]:
        """All changed files of a PR (follows pagination)."""
        files: list[PRFile] = []
        for page in range(1, _FILES_MAX_PAGES + 1):
            resp = await self._send(
                "GET",
                f"/repos/{owner}/{repo}/pulls/{pr_number}/files",
                installation_id=installation_id,
                params={"per_page": _FILES_PER_PAGE, "page": page},
            )
            try:
                batch = _PRFILES.validate_json(resp.content)
            except PydanticValidationError as exc:
                raise GitHubError("unexpected PR files response shape", resp.status_code) from exc
            files.extend(batch)
            if len(batch) < _FILES_PER_PAGE:
                break
        return files

    async def get_pr_diff(
        self, owner: str, repo: str, pr_number: int, *, installation_id: int
    ) -> str:
        resp = await self._send(
            "GET",
            f"/repos/{owner}/{repo}/pulls/{pr_number}",
            installation_id=installation_id,
            accept=_ACCEPT_DIFF,
        )
        return resp.text

    async def post_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        review: ReviewPayload,
        *,
        installation_id: int,
    ) -> None:
        await self._send(
            "POST",
            f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews",
            installation_id=installation_id,
            json_body=review.model_dump(mode="json", exclude_none=True),
        )

    async def post_comment(
        self, owner: str, repo: str, pr_number: int, body: str, *, installation_id: int
    ) -> None:
        await self._send(
            "POST",
            f"/repos/{owner}/{repo}/issues/{pr_number}/comments",
            installation_id=installation_id,
            json_body={"body": body},
        )
