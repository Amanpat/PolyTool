"""Bulk-path rate pacing (DR-2 Batch-Seed Top-200 Corpus).

A small, OPTIONAL, config-driven inter-step delay for the *aggressive bulk* code
paths — the leaderboard page loop and the wallet-scan batch loop — so a
200-wallet seed run stays polite against ``data-api.polymarket.com``.

Design contract (HARD):
  * Default OFF. ``BulkPacer.disabled()`` (and a config with ``enabled: false``,
    the shipped default) sleeps ZERO and makes ZERO sleep calls. The existing
    retry/backoff in ``HttpClient`` is unchanged; this only adds a steady-state
    spacer when explicitly enabled.
  * The gentle scheduler cadence is UNAFFECTED: pacing is only wired into the
    bulk export + wallet-scan batch paths. The scheduler's ``queue_drain`` and
    Loop A never construct a non-disabled pacer.
  * Operator-tunable from ``config/discovery_scheduler.json`` under the
    ``bulk_pacing`` key (no code change to retune).

This is a fixed-delay spacer (a degenerate token bucket with capacity 1): it
ensures at least ``delay_seconds`` elapse between successive ``pace()`` calls,
sleeping only for the remaining time if the caller was already slow.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable, Optional

_DEFAULT_CONFIG_PATH = Path("config") / "discovery_scheduler.json"

# Conservative shipped default IF an operator turns pacing on without tuning.
_DEFAULT_DELAY_SECONDS = 0.5


class BulkPacer:
    """Minimum-interval spacer between bulk requests. Default-off and harmless.

    Parameters
    ----------
    delay_seconds:
        Minimum seconds between successive ``pace()`` calls.
    enabled:
        When False (default), ``pace()`` is a no-op and never sleeps.
    sleep_fn / monotonic_fn:
        Injection seams for deterministic tests (default: real ``time``).
    """

    def __init__(
        self,
        delay_seconds: float = _DEFAULT_DELAY_SECONDS,
        *,
        enabled: bool = False,
        sleep_fn: Callable[[float], None] = time.sleep,
        monotonic_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self.delay_seconds = max(0.0, float(delay_seconds))
        # A zero/negative delay is functionally disabled even if enabled=True.
        self.enabled = bool(enabled) and self.delay_seconds > 0.0
        self._sleep = sleep_fn
        self._monotonic = monotonic_fn
        self._last_ts: Optional[float] = None

    @classmethod
    def disabled(cls) -> "BulkPacer":
        """An explicitly inert pacer (never sleeps). Use on the scheduler path."""
        return cls(0.0, enabled=False)

    def pace(self) -> float:
        """Sleep just long enough to honour the minimum interval.

        Returns the number of seconds actually slept (0.0 when disabled or when
        enough time already elapsed since the previous call).
        """
        if not self.enabled:
            return 0.0
        now = self._monotonic()
        if self._last_ts is None:
            # First call establishes the cadence anchor; do not front-load a sleep.
            self._last_ts = now
            return 0.0
        elapsed = now - self._last_ts
        remaining = self.delay_seconds - elapsed
        if remaining > 0:
            self._sleep(remaining)
            self._last_ts = self._monotonic()
            return remaining
        self._last_ts = now
        return 0.0


def load_bulk_pacing(
    config_path: Optional[Path] = None,
    *,
    sleep_fn: Callable[[float], None] = time.sleep,
    monotonic_fn: Callable[[], float] = time.monotonic,
) -> BulkPacer:
    """Build a BulkPacer from ``config/discovery_scheduler.json`` (default OFF).

    Reads the optional ``bulk_pacing`` object:
        {"enabled": false, "delay_seconds": 0.5}
    Any missing/unparseable config yields a disabled pacer (fail-safe: never
    accidentally throttle, never accidentally hammer because a key was absent —
    absence means OFF, which is the polite-by-omission default the scheduler
    relies on).
    """
    path = Path(config_path) if config_path is not None else _DEFAULT_CONFIG_PATH
    cfg: dict = {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        section = raw.get("bulk_pacing")
        if isinstance(section, dict):
            cfg = section
    except (FileNotFoundError, ValueError, OSError):
        cfg = {}

    enabled = bool(cfg.get("enabled", False))
    try:
        delay = float(cfg.get("delay_seconds", _DEFAULT_DELAY_SECONDS))
    except (TypeError, ValueError):
        delay = _DEFAULT_DELAY_SECONDS

    return BulkPacer(
        delay,
        enabled=enabled,
        sleep_fn=sleep_fn,
        monotonic_fn=monotonic_fn,
    )
