"""Token-bucket rate limiter for the live execution layer.

The bucket refills at a steady rate of `max_per_minute` tokens per minute.
Callers may block (``acquire``) or probe non-blocking (``try_acquire``).

Time injection via ``_clock`` lets tests avoid real sleeps by monkeypatching.
"""

from __future__ import annotations

import time
from typing import Callable


class TokenBucketRateLimiter:
    """Token-bucket rate limiter.

    Args:
        max_per_minute: Maximum number of tokens (actions) allowed per minute.
        _clock:         Optional callable returning current time in seconds.
                        Defaults to ``time.monotonic``.  Inject a fake clock
                        in tests to avoid real sleeping.
    """

    def __init__(
        self,
        max_per_minute: int,
        *,
        _clock: Callable[[], float] | None = None,
        _sleep: Callable[[float], None] | None = None,
    ) -> None:
        if max_per_minute <= 0:
            raise ValueError(f"max_per_minute must be > 0, got {max_per_minute}")
        self.max_per_minute = max_per_minute
        self._rate_per_second: float = max_per_minute / 60.0
        self._tokens: float = float(max_per_minute)
        self._clock: Callable[[], float] = _clock or time.monotonic
        self._sleep: Callable[[float], None] = _sleep or time.sleep
        self._last_refill: float = self._clock()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _refill(self) -> None:
        """Add tokens proportional to elapsed time since last refill."""
        now = self._clock()
        elapsed = now - self._last_refill
        if elapsed > 0:
            self._tokens = min(
                float(self.max_per_minute),
                self._tokens + elapsed * self._rate_per_second,
            )
            self._last_refill = now

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def try_acquire(self, n: int = 1) -> bool:
        """Non-blocking token acquisition.

        Returns:
            True if ``n`` tokens were successfully consumed, False otherwise.
        """
        if n <= 0:
            raise ValueError(f"n must be > 0, got {n}")
        self._refill()
        if self._tokens >= n:
            self._tokens -= n
            return True
        return False

    def acquire(self, n: int = 1) -> None:
        """Blocking token acquisition.  Sleeps the minimum time needed.

        Args:
            n: Number of tokens to acquire.
        """
        if n <= 0:
            raise ValueError(f"n must be > 0, got {n}")
        while True:
            self._refill()
            if self._tokens >= n:
                self._tokens -= n
                return
            # Sleep just long enough for n tokens to become available.
            deficit = n - self._tokens
            wait = deficit / self._rate_per_second
            self._sleep(wait)
