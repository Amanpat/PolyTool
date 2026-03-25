"""Market availability watcher for crypto pair bot — Track 2 / Phase 1A.

Wraps discover_crypto_pair_markets with availability evaluation logic so the
operator can check or poll for eligible BTC/ETH/SOL 5m/15m binary markets
without running the full paper runner.

DRY-RUN ONLY — no orders are placed here.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional, Tuple

from packages.polymarket.crypto_pairs.market_discovery import discover_crypto_pair_markets


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class AvailabilitySummary:
    """Result of one availability check against the Gamma API."""

    eligible_now: bool
    total_eligible: int
    by_symbol: dict  # e.g. {"BTC": 0, "ETH": 0, "SOL": 0}
    by_duration: dict  # e.g. {"5m": 0, "15m": 0}
    first_eligible_slugs: list  # up to 5 slugs, empty list when none
    rejection_reason: Optional[str]  # human-readable when eligible_now=False
    checked_at: str  # ISO UTC timestamp


# ---------------------------------------------------------------------------
# Core availability check
# ---------------------------------------------------------------------------

def _utcnow_iso() -> str:
    """Return current UTC timestamp as ISO 8601 string (no microseconds)."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run_availability_check(
    gamma_client=None,
    max_pages: int = 5,
    page_size: int = 100,
) -> AvailabilitySummary:
    """Check whether eligible BTC/ETH/SOL 5m/15m binary markets exist right now.

    Calls discover_crypto_pair_markets directly — does NOT fork the classifier.

    Args:
        gamma_client: Injected GammaClient for testing (default: live).
        max_pages: Maximum pagination pages to fetch.
        page_size: Markets per page.

    Returns:
        :class:`AvailabilitySummary` with counts, slugs, and eligibility flag.
    """
    markets = discover_crypto_pair_markets(
        gamma_client=gamma_client,
        max_pages=max_pages,
        page_size=page_size,
    )

    by_symbol: dict = {"BTC": 0, "ETH": 0, "SOL": 0}
    by_duration: dict = {"5m": 0, "15m": 0}

    for m in markets:
        if m.symbol in by_symbol:
            by_symbol[m.symbol] += 1
        duration_key = f"{m.duration_min}m"
        if duration_key in by_duration:
            by_duration[duration_key] += 1

    total_eligible = len(markets)
    eligible_now = total_eligible > 0
    first_eligible_slugs = [m.slug for m in markets[:5]]
    rejection_reason = (
        None
        if eligible_now
        else "No active BTC/ETH/SOL 5m/15m binary pair markets found"
    )

    return AvailabilitySummary(
        eligible_now=eligible_now,
        total_eligible=total_eligible,
        by_symbol=by_symbol,
        by_duration=by_duration,
        first_eligible_slugs=first_eligible_slugs,
        rejection_reason=rejection_reason,
        checked_at=_utcnow_iso(),
    )


# ---------------------------------------------------------------------------
# Watch loop
# ---------------------------------------------------------------------------

def run_watch_loop(
    *,
    poll_interval_seconds: int = 60,
    timeout_seconds: int = 3600,
    gamma_client=None,
    _sleep_fn: Optional[Callable[[float], None]] = None,
    _check_fn: Optional[Callable[[], AvailabilitySummary]] = None,
) -> Tuple[bool, AvailabilitySummary]:
    """Poll for eligible markets until one is found or the timeout expires.

    Args:
        poll_interval_seconds: Seconds to wait between polls.
        timeout_seconds: Total seconds before giving up and returning False.
        gamma_client: Injected GammaClient for testing (default: live).
        _sleep_fn: Replaces time.sleep for offline tests.
        _check_fn: Replaces run_availability_check for offline tests.

    Returns:
        ``(found, last_summary)`` — found=True when eligible_now=True was seen
        before the timeout, found=False when timeout elapsed without eligible
        markets.
    """
    sleep_fn = _sleep_fn if _sleep_fn is not None else time.sleep
    check_fn = (
        _check_fn
        if _check_fn is not None
        else lambda: run_availability_check(gamma_client=gamma_client)
    )

    deadline = time.monotonic() + timeout_seconds
    last_summary: Optional[AvailabilitySummary] = None

    while True:
        summary = check_fn()
        last_summary = summary

        if summary.eligible_now:
            return True, summary

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False, summary

        sleep_secs = min(poll_interval_seconds, remaining)
        sleep_fn(sleep_secs)

        # Re-check deadline after sleeping (handles short remaining windows)
        if time.monotonic() >= deadline:
            return False, last_summary
