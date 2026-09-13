import time
from collections.abc import Awaitable, Callable

from redis.asyncio import Redis

FetchToken = Callable[[int], Awaitable[tuple[str, float]]]


class InstallationTokenCache:
    """Two-layer (L1 in-memory + L2 Redis) cache of installation tokens."""

    def __init__(
        self,
        redis: Redis,
        private_key: str = "",
        app_id: int = 0,
        fetch_token: FetchToken | None = None,
    ) -> None:
        self._local: dict[int, tuple[str, float]] = {}
        self._redis = redis
        self._private_key = private_key
        self._app_id = app_id
        self._fetch_token = fetch_token  # injected for testing

    def _redis_key(self, installation_id: int) -> str:
        return f"meridian:install_token:{installation_id}"

    async def get_token(self, installation_id: int) -> str:
        """L1 → L2 → fetch from GitHub API, writing to both layers."""
        now = time.time()
        # 1. L1 fast path
        entry = self._local.get(installation_id)
        if entry and entry[1] > now:
            return entry[0]
        # 2. L2 Redis
        key = self._redis_key(installation_id)
        token = await self._redis.get(key)
        if token:
            ttl = await self._redis.ttl(key)
            expires = now + max(ttl, 0)
            cached = str(token)
            self._local[installation_id] = (cached, expires)
            return cached
        # 3. Cache miss → fetch
        token, expires_at = await self._fetch_from_github(installation_id)
        ttl = max(int(expires_at - now - 60), 60)
        await self._redis.set(key, token, ex=ttl)
        self._local[installation_id] = (token, expires_at)
        return token

    async def invalidate(self, installation_id: int) -> None:
        """Delete L2 key (propagates) and clear L1 entry."""
        await self._redis.delete(self._redis_key(installation_id))
        self._local.pop(installation_id, None)

    async def _fetch_from_github(self, installation_id: int) -> tuple[str, float]:
        if self._fetch_token:
            return await self._fetch_token(installation_id)
        raise NotImplementedError("fetch_token not configured")
