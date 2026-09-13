import pytest
from packages.github.token_cache import InstallationTokenCache


def test_cache_key_format():
    cache = InstallationTokenCache.__new__(InstallationTokenCache)
    assert cache._redis_key(12345) == "meridian:install_token:12345"


@pytest.mark.asyncio
async def test_l1_hit_no_network():
    from redis.asyncio import Redis

    cache = InstallationTokenCache(redis=Redis())  # won't be called
    cache._local = {12345: ("token-abc", 9999999999.0)}
    token = await cache.get_token(12345)
    assert token == "token-abc"  # noqa: S105 — fake test value
