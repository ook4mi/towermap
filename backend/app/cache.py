"""Simple in-memory TTL cache for collected TowerMap snapshots."""

from collections.abc import Awaitable, Callable
from time import monotonic
from typing import Any


class TTLCache[T]:
    """Minimal key-value TTL cache supporting async loaders and manual invalidation."""

    def __init__(self, ttl_seconds: int = 15) -> None:
        self._ttl_seconds = max(0, ttl_seconds)
        self._store: dict[str, tuple[float, T]] = {}

    @property
    def ttl_seconds(self) -> int:
        return self._ttl_seconds

    def get(self, key: str) -> T | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if monotonic() >= expires_at:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: T) -> T:
        if self._ttl_seconds > 0:
            self._store[key] = (monotonic() + self._ttl_seconds, value)
        return value

    async def get_or_load(self, key: str, loader: Callable[[], Awaitable[T]]) -> T:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = await loader()
        return self.set(key, value)

    def invalidate(self, key: str | None = None) -> None:
        if key is None:
            self._store.clear()
        else:
            self._store.pop(key, None)

    def stats(self) -> dict[str, Any]:
        return {"entries": len(self._store), "ttl_seconds": self._ttl_seconds}
