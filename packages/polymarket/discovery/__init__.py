"""Wallet Discovery v1 — Loop A plumbing and MVF scan-side.

This package provides the storage layer (ClickHouse DDL via 27_wallet_discovery.sql),
typed models, lifecycle state machine, leaderboard fetcher, churn detector,
scan queue manager, Loop A orchestrator, and MVF (Multi-Variate Fingerprint)
computation.

SPEC: docs/specs/SPEC-wallet-discovery-v1.md (frozen 2026-04-09)
Packets: A (commit 83832e1) — Loop A storage + plumbing
         B (commit 724a23c) — MVF computation + scan --quick
"""
from __future__ import annotations

from packages.polymarket.discovery.models import (
    LifecycleState,
    ReviewStatus,
    QueueState,
    InvalidTransitionError,
    validate_transition,
    WatchlistRow,
    LeaderboardSnapshotRow,
    ScanQueueRow,
)
from packages.polymarket.discovery.mvf import (
    compute_mvf,
    MvfResult,
    mvf_to_dict,
)

__all__ = [
    # Loop A models (8 symbols)
    "LifecycleState",
    "ReviewStatus",
    "QueueState",
    "InvalidTransitionError",
    "validate_transition",
    "WatchlistRow",
    "LeaderboardSnapshotRow",
    "ScanQueueRow",
    # MVF computation (3 symbols)
    "compute_mvf",
    "MvfResult",
    "mvf_to_dict",
]
