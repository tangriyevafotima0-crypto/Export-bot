"""Rate limiter for Telegram API calls."""
import asyncio
import time
from collections import deque


class RateLimiter:
    """Token bucket rate limiter for Telegram API.

    Telegram limits:
    - 30 msg/sec global
    - 1 msg/sec per private chat
    - 20 msg/min per group/channel
    """

    def __init__(self, max_calls: int = 30, period: float = 1.0):
        self.max_calls = max_calls
        self.period = period
        self._timestamps: deque = deque()
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Wait until a call can be made within rate limits."""
        async with self._lock:
            now = time.monotonic()

            # Remove timestamps outside the period window
            while self._timestamps and now - self._timestamps[0] > self.period:
                self._timestamps.popleft()

            # If at capacity, wait until the oldest call expires
            if len(self._timestamps) >= self.max_calls:
                wait_time = self.period - (now - self._timestamps[0])
                if wait_time > 0:
                    await asyncio.sleep(wait_time)

            self._timestamps.append(time.monotonic())

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, *args):
        pass


class AdaptiveRateLimiter(RateLimiter):
    """Rate limiter that adapts based on FloodWait errors."""

    def __init__(self, max_calls: int = 30, period: float = 1.0):
        super().__init__(max_calls, period)
        self._backoff_until: float = 0

    async def acquire(self):
        """Wait until a call can be made, respecting backoff."""
        now = time.monotonic()
        if now < self._backoff_until:
            await asyncio.sleep(self._backoff_until - now)

        await super().acquire()

    def report_flood_wait(self, wait_seconds: int):
        """Report a FloodWait error to trigger backoff."""
        self._backoff_until = time.monotonic() + wait_seconds
        # Reduce rate for future calls
        self.max_calls = max(1, self.max_calls // 2)

    def report_success(self):
        """Report successful call to potentially increase rate."""
        if self.max_calls < 30:
            self.max_calls = min(30, self.max_calls + 1)
