"""Minimal in-memory stand-in for the Redis Streams calls the consumer uses."""

import asyncio
from typing import Any

from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError


class FakeStreamRedis:
    """XGROUP CREATE / XREADGROUP / XACK with RESP2-shaped replies."""

    def __init__(self, resp3: bool = False) -> None:
        self.streams: dict[str, list[tuple[str, dict[str, str]]]] = {}
        self.delivered: dict[str, int] = {}
        self.acked: list[tuple[str, str, str]] = []
        self.groups: set[tuple[str, str]] = set()
        self.read_calls: list[dict[str, Any]] = []
        self.fail_reads = 0  # raise ConnectionError this many times
        self.fail_acks = 0
        self.group_error: Exception | None = None
        self.resp3 = resp3
        self._seq = 0

    def add(self, stream: str, data: str) -> str:
        self._seq += 1
        msg_id = f"{self._seq}-0"
        self.streams.setdefault(stream, []).append((msg_id, {"data": data}))
        return msg_id

    async def xgroup_create(self, name: str, groupname: str, id: str = "$", mkstream: bool = False):
        if self.group_error is not None:
            raise self.group_error
        if (name, groupname) in self.groups:
            raise ResponseError("BUSYGROUP Consumer Group name already exists")
        self.groups.add((name, groupname))
        self.streams.setdefault(name, [])

    async def xreadgroup(self, groupname, consumername, streams, count=None, block=None):
        self.read_calls.append({"streams": list(streams), "block": block})
        if self.fail_reads:
            self.fail_reads -= 1
            raise RedisConnectionError("boom")
        reply: list[Any] = []
        for stream in streams:
            start = self.delivered.get(stream, 0)
            entries = self.streams.get(stream, [])[start : start + (count or 10**9)]
            if entries:
                self.delivered[stream] = start + len(entries)
                reply.append([stream, [(i, dict(f)) for i, f in entries]])
        if not reply and block:
            await asyncio.sleep(0)  # yield; a real server would wait up to `block` ms
        if self.resp3:
            return {s: [e] for s, e in reply}
        return reply

    async def xack(self, name: str, groupname: str, *ids: str) -> int:
        if self.fail_acks:
            self.fail_acks -= 1
            raise RedisConnectionError("ack boom")
        for i in ids:
            self.acked.append((name, groupname, i))
        return len(ids)
