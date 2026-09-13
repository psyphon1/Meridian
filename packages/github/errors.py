class MeridianError(Exception):
    """Base exception for all Meridian errors."""


class GitHubError(MeridianError):
    """Base exception for all GitHub API errors."""

    def __init__(self, message: str, status_code: int = 0) -> None:
        super().__init__(message)
        self.status_code = status_code


class AuthenticationError(GitHubError):
    """401 — token invalid or expired."""


class RateLimitError(GitHubError):
    """429 or 403 with Retry-After — rate limited."""

    def __init__(self, message: str, retry_after: int = 0) -> None:
        super().__init__(message, status_code=429)
        self.retry_after = retry_after


class NotFoundError(GitHubError):
    """404 — resource not found."""


class ValidationError(GitHubError):
    """422 — GitHub rejected the request payload."""


class ServerError(GitHubError):
    """5xx — GitHub server error."""
