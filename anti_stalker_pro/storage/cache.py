"""In-memory cache with TTL support and asyncio-safe locking.

Provides a thread-safe, async-compatible cache for frequently accessed
data that reduces database query load.
"""

import asyncio
import time
from typing import Any, Callable, Awaitable, Optional

from core.logger import get_logger

logger = get_logger(__name__)


class CacheEntry:
    """A single cache entry with value and expiration timestamp."""

    __slots__ = ("value", "expires_at")

    def __init__(self, value: Any, ttl_seconds: float) -> None:
        """Initialize cache entry.

        Args:
            value: The cached value.
            ttl_seconds: Time-to-live in seconds (0 means no expiration).
        """
        self.value = value
        self.expires_at = time.monotonic() + ttl_seconds if ttl_seconds > 0 else float("inf")

    @property
    def is_expired(self) -> bool:
        """Check if this cache entry has expired."""
        return time.monotonic() > self.expires_at


class InMemoryCache:
    """Async-safe in-memory cache with TTL-based expiration.

    Uses asyncio.Lock for thread safety in async contexts.
    Expired entries are lazily cleaned up on access.
    """

    def __init__(self) -> None:
        """Initialize the cache with empty storage and a lock."""
        self._store: dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        """Retrieve a value from the cache.

        Returns None if the key does not exist or has expired.

        Args:
            key: Cache key to look up.

        Returns:
            The cached value, or None if not found/expired.
        """
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry.is_expired:
                del self._store[key]
                return None
            return entry.value

    async def set(self, key: str, value: Any, ttl_seconds: float = 300) -> None:
        """Store a value in the cache with a TTL.

        Args:
            key: Cache key.
            value: Value to store.
            ttl_seconds: Time-to-live in seconds (default 300s / 5min).
                Use 0 for no expiration.
        """
        async with self._lock:
            self._store[key] = CacheEntry(value, ttl_seconds)

    async def delete(self, key: str) -> bool:
        """Remove a key from the cache.

        Args:
            key: Cache key to remove.

        Returns:
            True if the key existed and was removed, False otherwise.
        """
        async with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    async def clear(self) -> int:
        """Remove all entries from the cache.

        Returns:
            int: Number of entries that were cleared.
        """
        async with self._lock:
            count = len(self._store)
            self._store.clear()
            logger.debug(f"Cache cleared: {count} entries removed")
            return count

    async def get_or_set(
        self, key: str, factory: Callable[[], Awaitable[Any]], ttl_seconds: float = 300
    ) -> Any:
        """Get a cached value or compute and store it if missing.

        If the key is not in the cache or has expired, calls the factory
        function to produce a value, stores it, and returns it.

        Args:
            key: Cache key.
            factory: Async callable that produces the value on cache miss.
            ttl_seconds: Time-to-live for newly stored values.

        Returns:
            The cached or freshly computed value.
        """
        value = await self.get(key)
        if value is not None:
            return value

        computed = await factory()
        await self.set(key, computed, ttl_seconds)
        return computed

    async def size(self) -> int:
        """Get the number of non-expired entries in the cache.

        Returns:
            int: Count of valid entries.
        """
        async with self._lock:
            now = time.monotonic()
            expired_keys = [k for k, v in self._store.items() if now > v.expires_at]
            for k in expired_keys:
                del self._store[k]
            return len(self._store)

    async def keys(self) -> list[str]:
        """Get all non-expired cache keys.

        Returns:
            list[str]: List of active cache keys.
        """
        async with self._lock:
            now = time.monotonic()
            return [k for k, v in self._store.items() if now <= v.expires_at]
