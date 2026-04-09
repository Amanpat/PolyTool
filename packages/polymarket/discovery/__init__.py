"""Wallet Discovery v1 — Loop A plumbing.

This package provides the storage layer (ClickHouse DDL via 27_wallet_discovery.sql),
typed models, lifecycle state machine, leaderboard fetcher, churn detector,
scan queue manager, and Loop A orchestrator.

SPEC: docs/specs/SPEC-wallet-discovery-v1.md (frozen 2026-04-09)
"""
from __future__ import annotations

try:
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

    __all__ = [
        "LifecycleState",
        "ReviewStatus",
        "QueueState",
        "InvalidTransitionError",
        "validate_transition",
        "WatchlistRow",
        "LeaderboardSnapshotRow",
        "ScanQueueRow",
    ]
except ImportError:
    # models.py is implemented in the Loop A plan (quick-260409-qez-loop-a).
    # This guard allows mvf.py and other scan-side modules to import without
    # requiring models.py to exist first.
    __all__ = []
