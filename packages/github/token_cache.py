"""Two-layer installation-token cache: L1 in-process dict + L2 Redis (spec §6.2, ADR-006 D5)."""

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

import structlog

#: Safety margin (seconds) subtracted from the token's real expiry in BOTH layers.
EXPIRY_MARGIN_S = 60

FetchToken = Callable[[int], Awaitable[tuple[str, float]]]

_log = structlog.get_logger("github.token_cache")


class TokenStore(Protocol):
    """The slice of ``redis.asyncio.Redis`` the cache needs (injectable for tests).

    Declared with plain ``def`` returning ``Awaitable`` because redis-py's own
    signatures are typed that way (sync/async shared stubs).
    """

    def get(self, name: str) -> Awaitable[Any]: ...

    def ttl(self, name: str) -> Awaitable[Any]: ...

    def set(self, name: str, value: str, ex: int | None = None) -> Awaitable[Any]: ...

    def delete(self, *names: str) -> Awaitable[Any]: ...


class InstallationTokenCache:
    """L1 → L2 → fetch cache of installation access tokens.

    L1 and L2 share one expiry: ``token_expiry - 60 s``. L2's Redis TTL is that
    remaining lifetime, and an L1 entry populated from L2 expires when the Redis
    key does, so a token is never served from L1 after Redis would have dropped it.
    ``store=None`` gives an L1-only cache (single process, no sharing).
    """

    def __init__(
        self,
        redis: TokenStore | None,
        fetch_token: FetchToken | None = None,
    ) -> None:
        self._local: dict[int, tuple[str, float]] = {}
        self._redis = redis
        self._fetch_token = fetch_token
        self._locks: dict[int, asyncio.Lock] = {}

    def set_fetcher(self, fetch_token: FetchToken) -> None:
        """Wire the network fetch (``GitHubClient`` does this on construction)."""
        self._fetch_token = fetch_token

    @property
    def has_fetcher(self) -> bool:
        return self._fetch_token is not None

    def _redis_key(self, installation_id: int) -> str:
        return f"meridian:install_token:{installation_id}"

    async def get_token(self, installation_id: int) -> str:
        """L1 → L2 Redis → fetch from GitHub, writing both layers on a miss."""
        cached = self._from_l1(installation_id)
        if cached is not None:
            return cached
        # Serialise concurrent misses per installation (avoid a fetch stampede).
        lock = self._locks.setdefault(installation_id, asyncio.Lock())
        async with lock:
            cached = self._from_l1(installation_id)
            if cached is not None:
                return cached
            cached = await self._from_l2(installation_id)
            if cached is not None:
                return cached
            return await self._fetch_and_store(installation_id)

    def _from_l1(self, installation_id: int) -> str | None:
        entry = self._local.get(installation_id)
        if entry and entry[1] > time.time():
            return entry[0]
        self._local.pop(installation_id, None)
        return None

    async def _from_l2(self, installation_id: int) -> str | None:
        if self._redis is None:
            return None
        key = self._redis_key(installation_id)
        raw = await self._redis.get(key)
        if not raw:
            return None
        ttl = int(await self._redis.ttl(key))
        if ttl <= 0:  # expired (-2) or no expiry (-1) between GET and TTL: treat as a miss
            return None
        token = raw.decode() if isinstance(raw, bytes) else str(raw)
        self._local[installation_id] = (token, time.time() + ttl)  # same expiry as L2
        return token

    async def _fetch_and_store(self, installation_id: int) -> str:
        if self._fetch_token is None:
            msg = "fetch_token not configured"
            raise NotImplementedError(msg)
        token, expires_at = await self._fetch_token(installation_id)
        ttl = int(expires_at - time.time()) - EXPIRY_MARGIN_S
        if ttl <= 0:
            # Too close to expiry to cache safely; hand it out once, uncached.
            _log.warning("token_cache.short_lived_token", installation_id=installation_id)
            return token
        if self._redis is not None:
            await self._redis.set(self._redis_key(installation_id), token, ex=ttl)
        self._local[installation_id] = (token, time.time() + ttl)
        return token

    async def invalidate(self, installation_id: int) -> None:
        """Delete the L2 key (propagates to all processes) and clear L1."""
        if self._redis is not None:
            await self._redis.delete(self._redis_key(installation_id))
        self._local.pop(installation_id, None)
