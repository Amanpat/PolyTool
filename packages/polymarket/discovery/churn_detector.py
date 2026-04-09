"""Churn detector for Wallet Discovery v1 — Loop A.

Compares two leaderboard snapshot sets to identify new wallets, dropped
wallets, persisting wallets, and rising wallets (rank improvement).

SPEC: docs/specs/SPEC-wallet-discovery-v1.md section "Loop A"
"""
from __future__ import annotations

from dataclasses import dataclass, field

from packages.polymarket.discovery.models import LeaderboardSnapshotRow


@dataclass
class ChurnResult:
    """Result of churn detection between two leaderboard snapshots."""
    new_wallets:        list[str]                          # in current, not in prior
    dropped_wallets:    list[str]                          # in prior, not in current
    persisting_wallets: list[str]                          # in both
    rising_wallets:     list[tuple[str, int, int]]         # (wallet, old_rank, new_rank) where new < old


def detect_churn(
    current_rows: list[LeaderboardSnapshotRow],
    prior_rows: list[LeaderboardSnapshotRow],
) -> ChurnResult:
    """Detect churn between the current and prior leaderboard snapshots.

    Args:
        current_rows: Snapshot rows for the current fetch run.
        prior_rows: Snapshot rows for the most recent prior fetch at the same
            (order_by, time_period, category) key. Pass empty list for the
            first-ever snapshot — all wallets will be treated as new.

    Returns:
        ChurnResult with new, dropped, persisting, and rising wallets.
    """
    prior_rank: dict[str, int] = {
        row.proxy_wallet: row.rank
        for row in prior_rows
        if row.proxy_wallet
    }
    current_rank: dict[str, int] = {
        row.proxy_wallet: row.rank
        for row in current_rows
        if row.proxy_wallet
    }

    prior_set = set(prior_rank.keys())
    current_set = set(current_rank.keys())

    new_wallets = sorted(current_set - prior_set)
    dropped_wallets = sorted(prior_set - current_set)
    persisting_wallets = sorted(current_set & prior_set)

    # Rising wallets: present in both; current rank < prior rank (lower number = better)
    rising_wallets: list[tuple[str, int, int]] = []
    for wallet in persisting_wallets:
        old_rank = prior_rank[wallet]
        new_rank = current_rank[wallet]
        if new_rank < old_rank:
            rising_wallets.append((wallet, old_rank, new_rank))

    # Sort rising by improvement magnitude (biggest jump first)
    rising_wallets.sort(key=lambda x: x[1] - x[2], reverse=True)

    return ChurnResult(
        new_wallets=new_wallets,
        dropped_wallets=dropped_wallets,
        persisting_wallets=persisting_wallets,
        rising_wallets=rising_wallets,
    )
