"""GitHubClient against httpx.MockTransport (no network)."""

import json
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from packages.github.client import GitHubClient, parse_retry_after
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
from packages.github.types import PRFile, ReviewComment, ReviewPayload

APP_ID = 4242
INSTALL = 99


@pytest.fixture(scope="module")
def keys() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    pub = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    return priv, pub


def iso(delta_s: int = 3600) -> str:
    return (datetime.now(UTC) + timedelta(seconds=delta_s)).strftime("%Y-%m-%dT%H:%M:%SZ")


class Server:
    """Scriptable fake GitHub: per-(method,path) queues of responses."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.script: dict[tuple[str, str], list[httpx.Response | Exception]] = {}
        self.token_counter = 0

    def on(self, method: str, path: str, *responses: httpx.Response | Exception) -> None:
        self.script.setdefault((method, path), []).extend(responses)

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        key = (request.method, request.url.path)
        if key[1].endswith("/access_tokens") and key not in self.script:
            self.token_counter += 1
            return httpx.Response(
                201, json={"token": f"inst-token-{self.token_counter}", "expires_at": iso()}
            )
        queue = self.script.get(key)
        if not queue:
            return httpx.Response(500, text=f"unscripted {key}")
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, Exception):
            raise item
        return item

    def calls(self, method: str, path: str) -> list[httpx.Request]:
        return [r for r in self.requests if (r.method, r.url.path) == (method, path)]


@pytest.fixture
def server() -> Server:
    return Server()


@pytest.fixture
def sleeps() -> list[float]:
    return []


@pytest.fixture
def make_client(server, sleeps, keys):
    clients: list[GitHubClient] = []

    def factory(cache: InstallationTokenCache | None = None, **kw) -> GitHubClient:
        async def fake_sleep(s: float) -> None:
            sleeps.append(s)

        http = httpx.AsyncClient(transport=httpx.MockTransport(server.handler))
        client = GitHubClient(
            cache,
            private_key=keys[0],
            app_id=APP_ID,
            http_client=http,
            sleep=fake_sleep,
            jitter=lambda cap: cap,  # deterministic: full backoff
            **kw,
        )
        clients.append(client)
        return client

    return factory


def files_json(n: int, start: int = 0) -> list[dict]:
    return [
        {
            "filename": f"f{i}.py",
            "status": "modified",
            "additions": 1,
            "deletions": 0,
            "changes": 1,
            "sha": "abc",
            "patch": "@@",
            "extra": "ignored",
        }
        for i in range(start, start + n)
    ]


# --- construction / compat ---------------------------------------------


def test_client_base_url():
    assert GitHubClient(token_cache=None)._base_url() == "https://api.github.com"


async def test_aclose_only_closes_owned_client():
    c = GitHubClient(token_cache=None)
    c._client()
    await c.aclose()
    assert c._http is None
    injected = httpx.AsyncClient()
    c2 = GitHubClient(token_cache=None, http_client=injected)
    await c2.aclose()
    assert not injected.is_closed
    await injected.aclose()


# --- installation token minting (real fetch callback) -------------------


async def test_get_installation_token_posts_with_app_jwt(make_client, server, keys):
    client = make_client()
    token = await client.get_installation_token(INSTALL)
    assert token == "inst-token-1"  # noqa: S105
    [req] = server.calls("POST", f"/app/installations/{INSTALL}/access_tokens")
    bearer = req.headers["authorization"]
    assert bearer.startswith("Bearer ")
    claims = jwt.decode(
        bearer.removeprefix("Bearer "), keys[1], algorithms=["RS256"], options={"verify_iss": False}
    )
    assert claims["iss"] == str(APP_ID)
    # cached: second call does not hit the network again
    await client.get_installation_token(INSTALL)
    assert len(server.calls("POST", f"/app/installations/{INSTALL}/access_tokens")) == 1


async def test_supplied_cache_gets_real_fetcher_wired(make_client, server):
    cache = InstallationTokenCache(None)
    assert not cache.has_fetcher
    client = make_client(cache)
    assert cache.has_fetcher
    assert await client.get_installation_token(INSTALL) == "inst-token-1"


async def test_preconfigured_cache_fetcher_is_not_overridden(make_client):
    async def mine(_: int) -> tuple[str, float]:
        return "mine", 9999999999.0

    client = make_client(InstallationTokenCache(None, fetch_token=mine))
    assert await client.get_installation_token(1) == "mine"


async def test_token_endpoint_malformed_response(make_client, server):
    server.on("POST", f"/app/installations/{INSTALL}/access_tokens", httpx.Response(201, json={}))
    with pytest.raises(GitHubError, match="unexpected installation token"):
        await make_client().get_installation_token(INSTALL)


# --- authenticated calls & typed returns --------------------------------


async def test_get_pr_files_sets_installation_auth_and_returns_models(make_client, server):
    server.on("GET", "/repos/o/r/pulls/42/files", httpx.Response(200, json=files_json(2)))
    files = await make_client().get_pr_files("o", "r", 42, installation_id=INSTALL)
    assert all(isinstance(f, PRFile) for f in files)
    assert [f.filename for f in files] == ["f0.py", "f1.py"]
    req = server.calls("GET", "/repos/o/r/pulls/42/files")[0]
    assert req.headers["authorization"] == "token inst-token-1"
    assert req.headers["accept"] == "application/vnd.github+json"
    assert req.headers["x-github-api-version"]


async def test_get_pr_files_paginates(make_client, server):
    path = "/repos/o/r/pulls/1/files"
    server.on(
        "GET",
        path,
        httpx.Response(200, json=files_json(100)),
        httpx.Response(200, json=files_json(5, 100)),
    )
    files = await make_client().get_pr_files("o", "r", 1, installation_id=INSTALL)
    assert len(files) == 105
    pages = [r.url.params["page"] for r in server.calls("GET", path)]
    assert pages == ["1", "2"]


async def test_get_pr_files_bad_shape(make_client, server):
    server.on("GET", "/repos/o/r/pulls/1/files", httpx.Response(200, json=[{"nope": 1}]))
    with pytest.raises(GitHubError, match="unexpected PR files"):
        await make_client().get_pr_files("o", "r", 1, installation_id=INSTALL)


async def test_get_pr_diff_uses_diff_media_type(make_client, server):
    server.on("GET", "/repos/o/r/pulls/3", httpx.Response(200, text="diff --git a b"))
    diff = await make_client().get_pr_diff("o", "r", 3, installation_id=INSTALL)
    assert diff == "diff --git a b"
    assert server.calls("GET", "/repos/o/r/pulls/3")[0].headers["accept"].endswith("v3.diff")


async def test_post_review_serialises_typed_payload(make_client, server):
    server.on("POST", "/repos/o/r/pulls/3/reviews", httpx.Response(200, json={}))
    review = ReviewPayload(
        body="summary",
        commit_id="abc123",
        comments=[ReviewComment(path="a.py", body="x", line=5)],
    )
    await make_client().post_review("o", "r", 3, review, installation_id=INSTALL)
    sent = json.loads(server.calls("POST", "/repos/o/r/pulls/3/reviews")[0].content)
    assert sent == {
        "body": "summary",
        "event": "COMMENT",
        "commit_id": "abc123",
        "comments": [{"path": "a.py", "body": "x", "line": 5, "side": "RIGHT"}],
    }


def test_review_payload_cannot_approve():
    with pytest.raises(ValueError):
        ReviewPayload(event="APPROVE")  # type: ignore[arg-type]


async def test_post_comment(make_client, server):
    server.on("POST", "/repos/o/r/issues/3/comments", httpx.Response(201, json={}))
    await make_client().post_comment("o", "r", 3, "hi", installation_id=INSTALL)
    sent = json.loads(server.calls("POST", "/repos/o/r/issues/3/comments")[0].content)
    assert sent == {"body": "hi"}


# --- 401 handling ---------------------------------------------------------


async def test_401_invalidates_cache_and_retries_once_with_new_token(make_client, server):
    path = "/repos/o/r/pulls/1/files"
    server.on(
        "GET",
        path,
        httpx.Response(401, json={"message": "Bad credentials"}),
        httpx.Response(200, json=files_json(1)),
    )
    files = await make_client().get_pr_files("o", "r", 1, installation_id=INSTALL)
    assert len(files) == 1
    auths = [r.headers["authorization"] for r in server.calls("GET", path)]
    assert auths == ["token inst-token-1", "token inst-token-2"]  # refreshed token used


async def test_401_twice_raises_authentication_error(make_client, server):
    path = "/repos/o/r/pulls/1/files"
    server.on("GET", path, httpx.Response(401, text="Bad credentials"))
    with pytest.raises(AuthenticationError):
        await make_client().get_pr_files("o", "r", 1, installation_id=INSTALL)
    assert len(server.calls("GET", path)) == 2  # exactly one retry


async def test_401_on_token_mint_is_not_retried(make_client, server):
    server.on("POST", f"/app/installations/{INSTALL}/access_tokens", httpx.Response(401, text="x"))
    with pytest.raises(AuthenticationError):
        await make_client().get_installation_token(INSTALL)
    assert len(server.calls("POST", f"/app/installations/{INSTALL}/access_tokens")) == 1


# --- 403 / rate limit ----------------------------------------------------


async def test_plain_403_is_authorization_error_not_rate_limit(make_client, server):
    server.on(
        "GET",
        "/repos/o/r/pulls/1/files",
        httpx.Response(
            403,
            json={"message": "Resource not accessible by integration"},
            headers={"x-ratelimit-remaining": "4999"},
        ),
    )
    with pytest.raises(AuthorizationError) as ei:
        await make_client().get_pr_files("o", "r", 1, installation_id=INSTALL)
    assert not isinstance(ei.value, RateLimitError)
    assert len(server.calls("GET", "/repos/o/r/pulls/1/files")) == 1  # no retry


async def test_403_with_retry_after_retries_then_succeeds(make_client, server, sleeps):
    path = "/repos/o/r/pulls/1/files"
    server.on(
        "GET",
        path,
        httpx.Response(403, headers={"Retry-After": "7"}, text="slow down"),
        httpx.Response(200, json=files_json(1)),
    )
    files = await make_client().get_pr_files("o", "r", 1, installation_id=INSTALL)
    assert len(files) == 1
    assert sleeps and sleeps[0] >= 7


async def test_403_with_remaining_zero_uses_reset_header(make_client, server, sleeps):
    import time

    path = "/repos/o/r/pulls/1/files"
    reset = str(int(time.time()) + 5)
    server.on(
        "GET",
        path,
        httpx.Response(403, headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": reset}),
        httpx.Response(200, json=files_json(1)),
    )
    await make_client().get_pr_files("o", "r", 1, installation_id=INSTALL)
    assert 3 <= sleeps[0] <= 6


async def test_429_exhausts_retries_with_exponential_backoff(make_client, server, sleeps):
    path = "/repos/o/r/pulls/1/files"
    server.on("GET", path, httpx.Response(429, headers={"Retry-After": "1"}, text="limit"))
    with pytest.raises(RateLimitError) as ei:
        await make_client().get_pr_files("o", "r", 1, installation_id=INSTALL)
    assert ei.value.retry_after == 1
    assert len(server.calls("GET", path)) == 4  # 1 + max 3 retries
    assert sleeps == [1.0, 2.0, 4.0]  # max(Retry-After, backoff) -> exponential


async def test_retry_after_longer_than_cap_raises_immediately(make_client, server, sleeps):
    server.on(
        "GET", "/repos/o/r/pulls/1/files", httpx.Response(429, headers={"Retry-After": "3600"})
    )
    with pytest.raises(RateLimitError) as ei:
        await make_client().get_pr_files("o", "r", 1, installation_id=INSTALL)
    assert ei.value.retry_after == 3600
    assert sleeps == []


async def test_post_is_retried_on_rate_limit(make_client, server):
    path = "/repos/o/r/issues/1/comments"
    server.on(
        "POST",
        path,
        httpx.Response(429, headers={"Retry-After": "1"}),
        httpx.Response(201, json={}),
    )
    await make_client().post_comment("o", "r", 1, "x", installation_id=INSTALL)
    assert len(server.calls("POST", path)) == 2


def test_parse_retry_after_forms():
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    assert parse_retry_after("30") == 30
    assert parse_retry_after(format_datetime(now + timedelta(seconds=90), usegmt=True), now) == 90
    assert parse_retry_after(format_datetime(now - timedelta(seconds=90), usegmt=True), now) == 0
    assert parse_retry_after("garbage") is None
    assert parse_retry_after(None) is None
    assert parse_retry_after("") is None


# --- 4xx / 5xx / transport -----------------------------------------------


@pytest.mark.parametrize(
    ("status", "exc"), [(404, NotFoundError), (422, ValidationError), (418, GitHubError)]
)
async def test_client_errors_map_to_typed_errors(make_client, server, status, exc):
    server.on("GET", "/repos/o/r/pulls/1/files", httpx.Response(status, text="nope"))
    with pytest.raises(exc) as ei:
        await make_client().get_pr_files("o", "r", 1, installation_id=INSTALL)
    assert ei.value.status_code == status


async def test_get_retries_5xx_with_backoff_then_succeeds(make_client, server, sleeps):
    path = "/repos/o/r/pulls/1/files"
    server.on("GET", path, httpx.Response(502), httpx.Response(503), httpx.Response(200, json=[]))
    assert await make_client().get_pr_files("o", "r", 1, installation_id=INSTALL) == []
    assert sleeps == [1.0, 2.0]


async def test_5xx_exhaustion_raises_server_error(make_client, server):
    server.on("GET", "/repos/o/r/pulls/1/files", httpx.Response(500, text="boom"))
    with pytest.raises(ServerError) as ei:
        await make_client().get_pr_files("o", "r", 1, installation_id=INSTALL)
    assert ei.value.status_code == 500
    assert len(server.calls("GET", "/repos/o/r/pulls/1/files")) == 4


async def test_post_is_not_retried_on_5xx(make_client, server):
    path = "/repos/o/r/pulls/1/reviews"
    server.on("POST", path, httpx.Response(500, text="boom"))
    with pytest.raises(ServerError):
        await make_client().post_review("o", "r", 1, ReviewPayload(), installation_id=INSTALL)
    assert len(server.calls("POST", path)) == 1


async def test_transport_errors_retried_then_typed(make_client, server):
    path = "/repos/o/r/pulls/1/files"
    server.on("GET", path, httpx.ConnectError("down"))
    with pytest.raises(TransportError):
        await make_client().get_pr_files("o", "r", 1, installation_id=INSTALL)
    assert len(server.calls("GET", path)) == 4


async def test_log_does_not_leak_token(make_client, server, capsys):
    server.on("GET", "/repos/o/r/pulls/1/files", httpx.Response(401, text="Bad credentials"))
    with pytest.raises(AuthenticationError):
        await make_client().get_pr_files("o", "r", 1, installation_id=INSTALL)
    out = capsys.readouterr()
    assert "inst-token" not in out.out + out.err
