"""InstallationTokenCache: L1, L2 (Redis protocol), miss/fetch, invalidate, expiry coherence."""

import time

import pytest
from packages.github.token_cache import EXPIRY_MARGIN_S, InstallationTokenCache


class FakeStore:
    """Dict-backed TokenStore that records TTLs (seconds)."""

    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self.ttls: dict[str, int] = {}
        self.calls: list[str] = []

    async def get(self, name):
        self.calls.append("get")
        return self.data.get(name)

    async def ttl(self, name):
        self.calls.append("ttl")
        return self.ttls.get(name, -2)

    async def set(self, name, value, ex=None):
        self.calls.append("set")
        self.data[name] = value
        self.ttls[name] = ex

    async def delete(self, *names):
        self.calls.append("delete")
        for n in names:
            self.data.pop(n, None)
            self.ttls.pop(n, None)


def make_fetch(value: str = "tok-1", lifetime: float = 3600.0):
    calls: list[int] = []

    async def fetch(installation_id: int) -> tuple[str, float]:
        calls.append(installation_id)
        return value, time.time() + lifetime

    return fetch, calls


def test_cache_key_format():
    assert InstallationTokenCache(None)._redis_key(12345) == "meridian:install_token:12345"


async def test_l1_hit_no_network_no_redis():
    store = FakeStore()
    cache = InstallationTokenCache(store)
    cache._local = {12345: ("token-abc", time.time() + 100)}
    assert await cache.get_token(12345) == "token-abc"
    assert store.calls == []


async def test_miss_fetches_and_writes_both_layers_with_same_expiry():
    store = FakeStore()
    fetch, calls = make_fetch(lifetime=3600)
    cache = InstallationTokenCache(store, fetch_token=fetch)
    before = time.time()
    assert await cache.get_token(7) == "tok-1"
    assert calls == [7]
    key = cache._redis_key(7)
    assert store.data[key] == "tok-1"
    ttl = store.ttls[key]
    assert abs(ttl - (3600 - EXPIRY_MARGIN_S)) <= 2
    # L1 expiry == L2 TTL expiry (both already minus the 60 s margin)
    l1_expiry = cache._local[7][1]
    assert abs(l1_expiry - (before + ttl)) <= 2
    # second call served from L1: no further fetch
    assert await cache.get_token(7) == "tok-1"
    assert calls == [7]


async def test_l2_hit_populates_l1_with_redis_ttl_and_skips_fetch():
    store = FakeStore()
    key = "meridian:install_token:9"
    store.data[key], store.ttls[key] = "shared-tok", 120
    fetch, calls = make_fetch()
    cache = InstallationTokenCache(store, fetch_token=fetch)
    now = time.time()
    assert await cache.get_token(9) == "shared-tok"
    assert calls == []
    assert abs(cache._local[9][1] - (now + 120)) <= 2


async def test_l2_key_expiring_between_get_and_ttl_is_a_miss():
    store = FakeStore()
    store.data["meridian:install_token:9"] = "stale"  # no TTL entry -> ttl() == -2
    fetch, calls = make_fetch("fresh")
    cache = InstallationTokenCache(store, fetch_token=fetch)
    assert await cache.get_token(9) == "fresh"
    assert calls == [9]


async def test_l1_expired_entry_falls_through_to_l2():
    store = FakeStore()
    key = "meridian:install_token:3"
    store.data[key], store.ttls[key] = "from-l2", 500
    cache = InstallationTokenCache(store)
    cache._local[3] = ("old", time.time() - 1)
    assert await cache.get_token(3) == "from-l2"


async def test_invalidate_clears_l1_and_l2():
    store = FakeStore()
    fetch, calls = make_fetch()
    cache = InstallationTokenCache(store, fetch_token=fetch)
    await cache.get_token(5)
    await cache.invalidate(5)
    assert cache._redis_key(5) not in store.data
    assert 5 not in cache._local
    await cache.get_token(5)
    assert calls == [5, 5]


async def test_token_near_expiry_is_returned_but_not_cached():
    store = FakeStore()
    fetch, _ = make_fetch(lifetime=30)  # inside the 60 s safety margin
    cache = InstallationTokenCache(store, fetch_token=fetch)
    assert await cache.get_token(1) == "tok-1"
    assert store.data == {}
    assert cache._local == {}


async def test_l1_only_mode_without_store():
    fetch, calls = make_fetch()
    cache = InstallationTokenCache(None, fetch_token=fetch)
    await cache.get_token(1)
    await cache.get_token(1)
    assert calls == [1]
    await cache.invalidate(1)  # no store: must not raise
    await cache.get_token(1)
    assert calls == [1, 1]


async def test_bytes_value_from_redis_is_decoded():
    store = FakeStore()
    key = "meridian:install_token:2"
    store.data[key], store.ttls[key] = b"bytes-tok", 100  # type: ignore[assignment]
    cache = InstallationTokenCache(store)
    assert await cache.get_token(2) == "bytes-tok"


async def test_no_fetcher_configured_raises():
    cache = InstallationTokenCache(None)
    with pytest.raises(NotImplementedError):
        await cache.get_token(1)
