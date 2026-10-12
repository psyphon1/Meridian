"""In-memory stand-ins for Redis Streams + async SQLAlchemy sessions (unit tests only).

``FakeRedis`` implements just the stream commands the worker uses, with Redis'
semantics for delivery counters (``XREADGROUP``-history and ``XAUTOCLAIM`` both
increment) so unit tests exercise the real decision logic. Real-server behaviour
is covered by ``tests/integration/test_janitor_redis.py``.
"""

import asyncio
from collections.abc import Callable
from typing import Any

from redis.exceptions import ResponseError


def _pid(entry_id: str) -> tuple[int, int]:
    ms, _, seq = entry_id.partition("-")
    return int(ms), int(seq or 0)


class FakeRedis:
    """Minimal async Redis Streams fake with one consumer group per stream."""

    def __init__(self, *, autoclaim_shape: str = "list3") -> None:
        self.streams: dict[str, list[tuple[str, dict[str, str]]]] = {}
        # stream -> group -> {"last": id, "pending": {id: [consumer, delivered_ms, count]}}
        self.groups: dict[str, dict[str, dict[str, Any]]] = {}
        self.now_ms = 1_000_000
        self._seq = 0
        self.autoclaim_shape = autoclaim_shape
        self.xtrim_calls: list[dict[str, Any]] = []
        self.fail_xadd_for: set[str] = set()
        self.closed = False
        self.xreadgroup_hook: Callable[[], None] | None = None

    # -- helpers ---------------------------------------------------------
    def advance(self, ms: int) -> None:
        self.now_ms += ms

    def _group(self, stream: str, group: str) -> dict[str, Any]:
        try:
            return self.groups[stream][group]
        except KeyError:
            raise ResponseError(
                f"NOGROUP No such key '{stream}' or consumer group '{group}'"
            ) from None

    # -- commands --------------------------------------------------------
    async def xadd(self, stream: str, fields: dict[str, str]) -> str:
        if stream in self.fail_xadd_for or fields.get("data") in self.fail_xadd_for:
            raise ResponseError("simulated XADD failure")
        self._seq += 1
        entry_id = f"{self.now_ms}-{self._seq}"
        self.streams.setdefault(stream, []).append((entry_id, dict(fields)))
        return entry_id

    async def xgroup_create(
        self, stream: str, group: str, id: str = "$", mkstream: bool = False
    ) -> bool:
        if group in self.groups.get(stream, {}):
            raise ResponseError("BUSYGROUP Consumer Group name already exists")
        self.streams.setdefault(stream, [])
        self.groups.setdefault(stream, {})[group] = {"last": "0-0", "pending": {}}
        return True

    async def xlen(self, stream: str) -> int:
        return len(self.streams.get(stream, []))

    async def xrange(
        self, stream: str, min: str = "-", max: str = "+", count: int | None = None
    ) -> list[tuple[str, dict[str, str]]]:
        rows = [
            e
            for e in self.streams.get(stream, [])
            if (min == "-" or _pid(e[0]) >= _pid(min)) and (max == "+" or _pid(e[0]) <= _pid(max))
        ]
        return rows[:count] if count else rows

    async def xreadgroup(
        self,
        groupname: str,
        consumername: str,
        streams: dict[str, str],
        count: int | None = None,
        block: int | None = None,
    ) -> list[list[Any]]:
        out: list[list[Any]] = []
        if self.xreadgroup_hook is not None:
            self.xreadgroup_hook()
        for stream, start in streams.items():
            grp = self._group(stream, groupname)
            entries: list[tuple[str, dict[str, str] | None]] = []
            if start == ">":
                for entry_id, fields in self.streams[stream]:
                    if _pid(entry_id) > _pid(grp["last"]):
                        grp["last"] = entry_id
                        grp["pending"][entry_id] = [consumername, self.now_ms, 1]
                        entries.append((entry_id, dict(fields)))
                        if count and len(entries) >= count:
                            break
                if not entries:
                    continue
            else:
                mine = sorted(
                    (i for i, p in grp["pending"].items() if p[0] == consumername), key=_pid
                )
                for entry_id in mine[: count or None]:
                    grp["pending"][entry_id][1] = self.now_ms
                    grp["pending"][entry_id][2] += 1
                    fields = dict(self.streams[stream]).get(entry_id)
                    entries.append((entry_id, fields))
            out.append([stream, entries])
        if block and not out:
            await asyncio.sleep(0.001)  # yield like a real blocking read
        return out

    async def xack(self, stream: str, group: str, *ids: str) -> int:
        grp = self._group(stream, group)
        return sum(1 for i in ids if grp["pending"].pop(i, None) is not None)

    async def xpending_range(
        self,
        stream: str,
        group: str,
        min: str = "-",
        max: str = "+",
        count: int = 10,
        idle: int | None = None,
    ) -> list[dict[str, Any]]:
        grp = self._group(stream, group)
        rows = []
        for entry_id in sorted(grp["pending"], key=_pid):
            consumer, delivered, n = grp["pending"][entry_id]
            if min.startswith("("):
                if _pid(entry_id) <= _pid(min[1:]):
                    continue
            elif min != "-" and _pid(entry_id) < _pid(min):
                continue
            if max != "+" and _pid(entry_id) > _pid(max):
                continue
            if idle is not None and self.now_ms - delivered < idle:
                continue
            rows.append(
                {
                    "message_id": entry_id,
                    "consumer": consumer,
                    "time_since_delivered": self.now_ms - delivered,
                    "times_delivered": n,
                }
            )
        return rows[:count]

    async def xpending(self, stream: str, group: str) -> dict[str, Any]:
        pend = sorted(self._group(stream, group)["pending"], key=_pid)
        return {
            "pending": len(pend),
            "min": pend[0] if pend else None,
            "max": pend[-1] if pend else None,
            "consumers": [],
        }

    async def xautoclaim(
        self,
        stream: str,
        group: str,
        consumer: str,
        min_idle_time: int,
        start_id: str = "0-0",
        count: int | None = None,
    ) -> Any:
        grp = self._group(stream, group)
        claimed: list[tuple[str, dict[str, str] | None]] = []
        data = dict(self.streams.get(stream, []))
        for entry_id in sorted(grp["pending"], key=_pid):
            if _pid(entry_id) < _pid(start_id):
                continue
            p = grp["pending"][entry_id]
            if self.now_ms - p[1] < min_idle_time:
                continue
            if count and len(claimed) >= count:
                return self._autoclaim_reply(entry_id, claimed)
            p[0], p[1], p[2] = consumer, self.now_ms, p[2] + 1
            claimed.append((entry_id, data.get(entry_id)))
        return self._autoclaim_reply("0-0", claimed)

    def _autoclaim_reply(self, cursor: str, claimed: list[Any]) -> Any:
        if self.autoclaim_shape == "tuple2":
            return (cursor, claimed)
        if self.autoclaim_shape == "tuple3":
            return (cursor, claimed, [])
        return [cursor, claimed, []]

    async def xinfo_groups(self, stream: str) -> list[dict[str, Any]]:
        if stream not in self.groups:
            raise ResponseError("ERR no such key")
        return [
            {"name": name, "pending": len(g["pending"]), "last-delivered-id": g["last"]}
            for name, g in self.groups[stream].items()
        ]

    async def xtrim(
        self,
        stream: str,
        maxlen: int | None = None,
        approximate: bool = True,
        minid: str | None = None,
    ) -> int:
        self.xtrim_calls.append({"stream": stream, "maxlen": maxlen, "minid": minid})
        rows = self.streams.get(stream, [])
        before = len(rows)
        if minid is not None:
            rows = [e for e in rows if _pid(e[0]) >= _pid(minid)]
        if maxlen is not None:
            rows = rows[-maxlen:] if maxlen else []
        self.streams[stream] = rows
        return before - len(rows)

    async def aclose(self) -> None:
        self.closed = True


class FakeSession:
    """Async-context-manager session recording executed statements."""

    def __init__(self, factory: "FakeSessionFactory") -> None:
        self.factory = factory

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *exc: object) -> None:
        self.factory.exited += 1

    def begin(self) -> "FakeSession":
        return self

    async def execute(self, statement: Any) -> Any:
        self.factory.statements.append(statement)
        return self.factory.result_for(statement)


class _Result:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> "_Result":
        return self

    def all(self) -> list[Any]:
        return self._rows

    def scalar_one_or_none(self) -> Any:
        return self._rows[0] if self._rows else None


class FakeSessionFactory:
    """Callable returning ``FakeSession``; SELECTs return ``rows``, others nothing."""

    def __init__(self, rows: list[Any] | None = None) -> None:
        self.rows = rows or []
        self.statements: list[Any] = []
        self.exited = 0

    def __call__(self) -> FakeSession:
        return FakeSession(self)

    def result_for(self, statement: Any) -> _Result:
        is_select = statement.__class__.__name__ == "Select"
        return _Result(self.rows if is_select else [])


async def eventually(predicate: Callable[[], Any], *, within_s: float = 5.0) -> None:
    """Poll ``predicate`` (sync or async) until truthy; fail the test after ``within_s``."""
    async with asyncio.timeout(within_s):
        while True:
            result = predicate()
            if asyncio.iscoroutine(result):
                result = await result
            if result:
                return
            await asyncio.sleep(0.005)
