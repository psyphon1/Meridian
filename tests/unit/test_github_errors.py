import pytest
from packages.github.errors import (
    AuthenticationError,
    GitHubError,
    MeridianError,
    NotFoundError,
    RateLimitError,
    ServerError,
)


def test_error_hierarchy():
    assert issubclass(GitHubError, MeridianError)
    assert issubclass(AuthenticationError, GitHubError)
    assert issubclass(RateLimitError, GitHubError)
    assert issubclass(NotFoundError, GitHubError)
    assert issubclass(ServerError, GitHubError)


def test_rate_limit_carries_retry_after():
    err = RateLimitError("rate limited", retry_after=120)
    assert err.retry_after == 120
    assert "rate limited" in str(err)


def test_errors_are_catchable_as_github_error():
    with pytest.raises(GitHubError):
        raise NotFoundError("missing")
