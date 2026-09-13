import pytest
from packages.github.client import GitHubClient


def test_client_base_url():
    client = GitHubClient.__new__(GitHubClient)
    assert client._base_url() == "https://api.github.com"


@pytest.mark.asyncio
async def test_get_pr_files_calls_http(monkeypatch):
    calls = []

    class FakeResp:
        status_code = 200

        def json(self):
            return [{"filename": "a.py", "sha": "abc"}]

    class FakeClient:
        async def get(self, url, **kw):
            calls.append(("GET", url, kw))
            return FakeResp()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

    monkeypatch.setattr("packages.github.client.httpx.AsyncClient", lambda **kw: FakeClient())
    client = GitHubClient(token_cache=None, private_key="k", app_id=1)
    files = await client.get_pr_files("owner", "repo", 42)
    assert files == [{"filename": "a.py", "sha": "abc"}]
    assert "pulls/42/files" in calls[0][1]
