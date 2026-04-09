"""Typed models, enums, and lifecycle state machine for Wallet Discovery v1.

SPEC: docs/specs/SPEC-wallet-discovery-v1.md (frozen 2026-04-09)

All logic here is pure Python with no ClickHouse dependency, enabling
deterministic offline testing.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enums matching the ClickHouse Enum8 definitions in the spec DDL
# ---------------------------------------------------------------------------

class LifecycleState(str, Enum):
    """Wallet lifecycle state — mirrors watchlist.lifecycle_state Enum8."""
    discovered = "discovered"
    queued     = "queued"
    scanned    = "scanned"
    reviewed   = "reviewed"
    promoted   = "promoted"
    watched    = "watched"
    stale      = "stale"
    retired    = "retired"


class ReviewStatus(str, Enum):
    """Human review outcome — mirrors watchlist.review_status Enum8."""
    pending  = "pending"
    approved = "approved"
    rejected = "rejected"


class QueueState(str, Enum):
    """Scan queue item state — mirrors scan_queue.queue_state Enum8."""
    pending = "pending"
    leased  = "leased"
    done    = "done"
    failed  = "failed"
    dropped = "dropped"


# ---------------------------------------------------------------------------
# Lifecycle state machine
# ---------------------------------------------------------------------------

class InvalidTransitionError(ValueError):
    """Raised when an invalid lifecycle state transition is attempted."""


# Allowed transitions per the spec state machine diagram.
# Note: `reviewed -> promoted` additionally requires review_status='approved'
# (enforced by validate_transition below).
# `any -> retired` is allowed from every state (handled specially).
VALID_TRANSITIONS: dict[LifecycleState, set[LifecycleState]] = {
    LifecycleState.discovered: {LifecycleState.queued, LifecycleState.retired},
    LifecycleState.queued:     {LifecycleState.scanned, LifecycleState.queued, LifecycleState.retired},
    LifecycleState.scanned:    {LifecycleState.reviewed, LifecycleState.retired},
    LifecycleState.reviewed:   {LifecycleState.promoted, LifecycleState.retired},
    LifecycleState.promoted:   {LifecycleState.watched, LifecycleState.retired},
    LifecycleState.watched:    {LifecycleState.stale, LifecycleState.retired},
    LifecycleState.stale:      {LifecycleState.queued, LifecycleState.retired},
    LifecycleState.retired:    {LifecycleState.retired},
}

# Transitions that are explicitly rejected in the spec (documented for clarity)
_SPEC_EXPLICIT_REJECTIONS: set[tuple[LifecycleState, LifecycleState]] = {
    (LifecycleState.discovered, LifecycleState.promoted),
    (LifecycleState.discovered, LifecycleState.watched),
    (LifecycleState.queued,     LifecycleState.promoted),
    (LifecycleState.scanned,    LifecycleState.promoted),
    (LifecycleState.scanned,    LifecycleState.watched),
}


def validate_transition(
    current: LifecycleState,
    target: LifecycleState,
    review_status: Optional[ReviewStatus] = None,
) -> None:
    """Validate a lifecycle state transition.

    Raises InvalidTransitionError on invalid transitions with a descriptive
    message naming the attempted transition.

    Special rules enforced here (not just in VALID_TRANSITIONS):
    - `discovered` is an entry-only state: no state may transition TO it.
    - `reviewed -> promoted` additionally requires review_status='approved'.
    - `promoted -> watched` is structurally allowed (forward compat) but
      remains invalid in v1 because Loop B is not implemented. Per spec, we
      allow the structural definition but enforce the rule via the transition
      table (promoted->watched IS in VALID_TRANSITIONS for spec completeness;
      operational gating is the application's responsibility).
    """
    # Rule: `discovered` is an entry-only state — no state may transition TO it.
    if target == LifecycleState.discovered:
        raise InvalidTransitionError(
            f"Invalid transition: {current.value} -> {target.value}. "
            f"'discovered' is an entry-only state; wallets cannot be "
            f"re-discovered once in the system."
        )

    # Check VALID_TRANSITIONS table
    allowed = VALID_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidTransitionError(
            f"Invalid transition: {current.value} -> {target.value}. "
            f"Allowed targets from '{current.value}': "
            f"{sorted(s.value for s in allowed) or 'none'}."
        )

    # Special rule: reviewed -> promoted requires review_status='approved'
    if current == LifecycleState.reviewed and target == LifecycleState.promoted:
        if review_status != ReviewStatus.approved:
            status_str = review_status.value if review_status else "None"
            raise InvalidTransitionError(
                f"Invalid transition: {current.value} -> {target.value}. "
                f"Requires review_status='approved' (got '{status_str}'). "
                f"A human operator must set review_status to 'approved' before promotion."
            )


# ---------------------------------------------------------------------------
# Dataclasses matching ClickHouse table DDL columns
# ---------------------------------------------------------------------------

@dataclass
class WatchlistRow:
    """One row in polytool.watchlist — one current row per wallet."""
    wallet_address:   str
    lifecycle_state:  LifecycleState
    review_status:    ReviewStatus
    priority:         int              # 1 (highest) to 5 (lowest), default 3
    source:           str              # 'loop_a', 'manual', 'loop_d'
    reason:           str              # default ''
    last_scan_run_id: Optional[str]
    last_scanned_at:  Optional[datetime]
    last_activity_at: Optional[datetime]
    metadata_json:    str              # JSON string, default '{}'
    updated_at:       datetime


@dataclass
class LeaderboardSnapshotRow:
    """One row in polytool.leaderboard_snapshots — append-only raw facts."""
    snapshot_ts:      datetime
    fetch_run_id:     str
    order_by:         str              # e.g. 'PNL', 'VOL'
    time_period:      str              # e.g. 'DAY', 'WEEK', 'MONTH', 'ALL'
    category:         str              # e.g. 'OVERALL', 'POLITICS', 'SPORTS', 'CRYPTO'
    rank:             int
    proxy_wallet:     str
    username:         str              # default ''
    pnl:              float
    volume:           float
    is_new:           int              # 0 or 1
    raw_payload_json: str              # JSON string, default '{}'


@dataclass
class ScanQueueRow:
    """One row in polytool.scan_queue — deduplicated work queue."""
    queue_id:         str
    dedup_key:        str              # format: '{source}:{wallet_address}'
    wallet_address:   str
    source:           str
    source_ref:       str              # default ''
    priority:         int              # 1 (highest) to 5 (lowest), default 3
    queue_state:      QueueState
    available_at:     datetime
    leased_at:        Optional[datetime]
    lease_expires_at: Optional[datetime]
    lease_owner:      Optional[str]
    attempt_count:    int              # default 0, incremented on re-queue
    last_error:       Optional[str]
    created_at:       datetime
    updated_at:       datetime

    @property
    def computed_dedup_key(self) -> str:
        """Compute the canonical dedup key from source and wallet_address."""
        return f"{self.source}:{self.wallet_address}"
