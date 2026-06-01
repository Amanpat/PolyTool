"""WI-4 candidate-tier auto-population + locked-tier immutability.

Two responsibilities, both pure / I/O-injectable so they test offline:

1. ``build_candidate_row(...)`` — given a wallet's deep-scan evidence, produce a
   CANDIDATE-tier ``WatchlistRow`` (tier='candidate', locked=0) carrying the
   deterministic evidence reason string. Candidate tier is SYSTEM-OWNED and is
   rewritten on every rescan.

2. ``LockedImmutabilityError`` + ``guard_not_locked(...)`` /
   ``filter_locked(...)`` — the single enforcement point that makes locked
   entries (``locked=1``, operator-set) immutable to EVERY automated path
   (worker advance, scheduler rescan, candidate population). Any automated write
   routes through ``protect_locked_writes`` which drops rows whose wallet is
   locked in the current watchlist snapshot, so a locked entry is byte-identical
   after a full discovery+rescan cycle (acceptance gate 2).

CRITICAL GATE PRESERVATION (acceptance gate 1)
----------------------------------------------
Candidate population fills ONLY the candidate tier and ONLY writes
``lifecycle_state='scanned'`` rows with ``review_status='pending'``. It NEVER
sets review_status to 'approved' and NEVER advances toward promoted/watched.
Promotion remains behind the human gate (``validate_transition`` with
review_status='approved'). There is no auto-promote path here.

No ClickHouse, no network in this module: the existing watchlist snapshot is
passed in (list of dicts) and the write callable is injected.

SPEC: docs/specs/SPEC-wallet-discovery-v1.md ; WI-4 work packet.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from packages.polymarket.discovery.evidence_summary import (
    Evidence,
    is_candidate,
    load_promotion_config,
    summarize_evidence,
)
from packages.polymarket.discovery.models import (
    LifecycleState,
    ReviewStatus,
    WatchlistRow,
)

logger = logging.getLogger(__name__)

TIER_CANDIDATE = "candidate"
TIER_LOCKED = "locked"


class LockedImmutabilityError(RuntimeError):
    """Raised when an automated path attempts to modify a locked watchlist entry."""


# ---------------------------------------------------------------------------
# Locked detection (the single source of truth for "is this wallet locked?")
# ---------------------------------------------------------------------------


def is_locked_row(row: "dict | WatchlistRow") -> bool:
    """True if a watchlist row is operator-locked (immutable to automation).

    A row is locked when ``locked`` is truthy (1/'1'/True/'true') OR ``tier``
    resolves to 'locked'. Tolerant of dicts (ClickHouse JSONEachRow) and
    WatchlistRow instances.
    """
    if isinstance(row, WatchlistRow):
        locked = row.locked
        tier = row.tier
    else:
        locked = row.get("locked")
        tier = row.get("tier")
    if locked in (1, "1", True, "true", "True"):
        return True
    if isinstance(tier, str) and tier.strip().lower() == TIER_LOCKED:
        return True
    return False


def locked_wallets(snapshot: Iterable[dict]) -> set[str]:
    """Return the set of wallet_addresses that are locked in a watchlist snapshot."""
    out: set[str] = set()
    for row in snapshot:
        wallet = row.get("wallet_address") if isinstance(row, dict) else getattr(row, "wallet_address", None)
        if wallet and is_locked_row(row):
            out.add(str(wallet))
    return out


def guard_not_locked(wallet_address: str, locked_set: set[str]) -> None:
    """Raise LockedImmutabilityError if ``wallet_address`` is in ``locked_set``.

    Call this at the top of any automated mutation path that targets a single
    wallet (e.g. the scan-worker watchlist advance) to enforce immutability.
    """
    if wallet_address in locked_set:
        raise LockedImmutabilityError(
            f"wallet {wallet_address} is operator-locked (locked=1); "
            f"automated paths must not modify or remove it"
        )


def filter_locked(
    rows: list[WatchlistRow],
    locked_set: set[str],
) -> tuple[list[WatchlistRow], list[str]]:
    """Split candidate write rows into (writable, dropped_locked_wallets).

    Drops any row whose wallet is locked. Returns the writable rows plus the
    list of wallet addresses that were dropped (for logging / reporting).
    """
    writable: list[WatchlistRow] = []
    dropped: list[str] = []
    for row in rows:
        if row.wallet_address in locked_set:
            dropped.append(row.wallet_address)
            continue
        writable.append(row)
    return writable, dropped


# ---------------------------------------------------------------------------
# Candidate-tier row construction
# ---------------------------------------------------------------------------


def build_candidate_row(
    evidence: "Evidence | dict",
    *,
    source: str = "loop_a",
    last_scan_run_id: Optional[str] = None,
    last_scanned_at: Optional[datetime] = None,
    now: Optional[datetime] = None,
) -> WatchlistRow:
    """Build a CANDIDATE-tier WatchlistRow from a wallet's deep-scan evidence.

    The row is tier='candidate', locked=0, lifecycle_state='scanned',
    review_status='pending' — i.e. fully inside the human gate. ``reason`` is the
    deterministic evidence summary. ``source`` preserves discovery ORIGIN
    ('loop_a' | 'manual' | 'loop_d'); it is NOT the tier (Fork #1).
    """
    ev = evidence if isinstance(evidence, Evidence) else Evidence.from_dict(evidence)
    now = now or datetime.now(timezone.utc)
    return WatchlistRow(
        wallet_address=ev.wallet_address,
        lifecycle_state=LifecycleState.scanned,
        review_status=ReviewStatus.pending,
        priority=3,
        source=source,
        reason=summarize_evidence(ev),
        last_scan_run_id=last_scan_run_id,
        last_scanned_at=last_scanned_at or now,
        last_activity_at=None,
        metadata_json="{}",
        updated_at=now,
        tier=TIER_CANDIDATE,
        locked=0,
    )


def plan_candidate_writes(
    evidences: list["Evidence | dict"],
    watchlist_snapshot: list[dict],
    *,
    source: str = "loop_a",
    config_path: Optional[Path] = None,
    now: Optional[datetime] = None,
) -> tuple[list[WatchlistRow], list[str]]:
    """Decide which scanned wallets become/refresh candidate-tier rows.

    Pure planning function (no I/O):
      1. Resolve thresholds from config (defensive).
      2. For each evidence, keep it iff ``is_candidate`` (OR-gate).
      3. Build a candidate WatchlistRow for each kept wallet.
      4. Drop any whose wallet is LOCKED in the current snapshot (immutability).

    Returns ``(writable_rows, dropped_locked_wallets)``.
    """
    cfg = load_promotion_config(config_path)
    thresholds = cfg["candidate_thresholds"]
    locked_set = locked_wallets(watchlist_snapshot)

    rows: list[WatchlistRow] = []
    for ev_in in evidences:
        ev = ev_in if isinstance(ev_in, Evidence) else Evidence.from_dict(ev_in)
        if not ev.wallet_address:
            continue
        if not is_candidate(ev, thresholds):
            continue
        rows.append(
            build_candidate_row(
                ev,
                source=source,
                now=now,
            )
        )

    writable, dropped = filter_locked(rows, locked_set)
    if dropped:
        logger.info(
            "candidate_population: skipped %d locked wallet(s) (immutable): %s",
            len(dropped),
            ", ".join(dropped),
        )
    return writable, dropped


def populate_candidates(
    evidences: list["Evidence | dict"],
    watchlist_snapshot: list[dict],
    write_rows: Callable[[list[WatchlistRow]], bool],
    *,
    source: str = "loop_a",
    config_path: Optional[Path] = None,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Plan + persist candidate-tier rows via an injected ``write_rows`` callable.

    ``write_rows`` is injected (e.g. a partial of clickhouse_writer.write_watchlist_rows
    bound with creds) so this stays ClickHouse-free and offline-testable.

    Returns a summary dict: ``{written, dropped_locked, ok}``.
    """
    rows, dropped = plan_candidate_writes(
        evidences,
        watchlist_snapshot,
        source=source,
        config_path=config_path,
        now=now,
    )
    ok = True
    if rows:
        ok = bool(write_rows(rows))
    return {
        "written": len(rows) if ok else 0,
        "dropped_locked": dropped,
        "ok": ok,
    }
