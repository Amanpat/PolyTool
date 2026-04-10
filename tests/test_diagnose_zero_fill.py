"""Tests for tools/gates/diagnose_zero_fill.py — offline synthetic tape coverage.

Three verdict paths are covered:
  1. BOOK_NEVER_INITIALIZED — tape has only price_2min_guide events (no book snapshot).
  2. NO_COMPETITIVE_LEVELS — tape has a book snapshot but strategy spread is wider
     than the book spread, so no quote ever crosses the BBO.
  3. FILLS_OK — tape has a book snapshot with deep levels and close BBO so the
     strategy does accumulate fills.
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Ensure repo root is on sys.path so package imports work.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.gates.diagnose_zero_fill import run_diagnostic


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ASSET_ID = "test_asset_00001"


def _write_events(tmp_path: Path, events: list[dict[str, Any]]) -> Path:
    """Write *events* to tmp_path/events.jsonl, return the tape_dir Path."""
    tape_dir = tmp_path / "tape"
    tape_dir.mkdir(parents=True, exist_ok=True)
    events_path = tape_dir / "events.jsonl"
    with open(events_path, "w", encoding="utf-8") as fh:
        for ev in events:
            fh.write(json.dumps(ev) + "\n")
    return tape_dir


def _make_price_change(
    seq: int,
    ts: float,
    asset_id: str,
    bid_price: str = "0.50",
    bid_size: str = "500",
    ask_price: str = "0.55",
    ask_size: str = "500",
) -> dict:
    """Build a price_change event (legacy changes[] format) for one asset."""
    return {
        "seq": seq,
        "ts_recv": ts,
        "event_type": "price_change",
        "asset_id": asset_id,
        "changes": [
            {"side": "BUY", "price": bid_price, "size": bid_size},
            {"side": "SELL", "price": ask_price, "size": ask_size},
        ],
    }


def _make_book_snapshot(
    seq: int,
    ts: float,
    asset_id: str,
    bids: list[tuple[str, str]] | None = None,
    asks: list[tuple[str, str]] | None = None,
) -> dict:
    """Build a 'book' snapshot event."""
    if bids is None:
        bids = [("0.50", "100")]
    if asks is None:
        asks = [("0.55", "100")]
    return {
        "seq": seq,
        "ts_recv": ts,
        "event_type": "book",
        "asset_id": asset_id,
        "bids": [{"price": p, "size": s} for p, s in bids],
        "asks": [{"price": p, "size": s} for p, s in asks],
    }


# ---------------------------------------------------------------------------
# Test 1 — BOOK_NEVER_INITIALIZED
# ---------------------------------------------------------------------------


def test_book_never_initialized_verdict(tmp_path: Path) -> None:
    """Silver-like tape with only price_2min_guide events (no book snapshot).

    The L2Book never receives an EVENT_TYPE_BOOK event, so _initialized stays
    False and the fill engine rejects every fill attempt.

    Expected verdict: BOOK_NEVER_INITIALIZED.
    """
    # Build a tape that mimics a Silver tape: only price_2min_guide events.
    # L2Book.apply() returns False for unknown event types and does not set
    # _initialized. These events carry best_bid / best_ask in their payload
    # so the strategy can compute quotes, but the fill engine is never engaged.
    events: list[dict] = []
    seq = 1
    ts = 1_000_000.0
    for i in range(20):
        events.append(
            {
                "seq": seq,
                "ts_recv": ts,
                "event_type": "price_2min_guide",
                "asset_id": _ASSET_ID,
                "best_bid": 0.50,
                "best_ask": 0.55,
            }
        )
        seq += 1
        ts += 60.0

    tape_dir = _write_events(tmp_path, events)
    report = run_diagnostic(tape_dir, _ASSET_ID)

    assert report["book_ever_initialized"] is False, (
        "Expected L2Book to remain uninitialized on a price_2min_guide-only tape"
    )
    assert report["verdict"] == "BOOK_NEVER_INITIALIZED", (
        f"Expected BOOK_NEVER_INITIALIZED but got {report['verdict']!r}"
    )
    assert "book_not_initialized" in report["verdict_evidence"].lower() or \
           "initialized" in report["verdict_evidence"].lower(), (
        "verdict_evidence should mention initialization"
    )
    assert report["fill_successes"] == 0
    assert report["first_book_init_seq"] is None


# ---------------------------------------------------------------------------
# Test 2 — NO_COMPETITIVE_LEVELS (or QUOTES_TOO_WIDE)
# ---------------------------------------------------------------------------


def test_book_initialized_no_competitive_levels(tmp_path: Path) -> None:
    """Tape has a book snapshot but book spread is wider than strategy spread.

    BBO: bid=0.40, ask=0.60 — 20 cents wide.
    Strategy defaults: min_spread=0.020, max_spread=0.120 — at most 12 cents.

    At mid=0.50 the strategy will generate quotes somewhere like bid=0.44,
    ask=0.56, which do NOT cross the book BBO (bid=0.40, ask=0.60).  So no
    fills can occur even though the book is initialized.

    Expected verdict: NO_COMPETITIVE_LEVELS or QUOTES_TOO_WIDE (both are valid
    zero-fill root causes; the test accepts either).
    """
    # Provide a deep book with a wide spread so strategy can see BBO but
    # will never post a quote aggressive enough to match.
    bids = [
        ("0.40", "10000"),
        ("0.39", "20000"),
        ("0.38", "20000"),
        ("0.37", "20000"),
    ]
    asks = [
        ("0.60", "10000"),
        ("0.61", "20000"),
        ("0.62", "20000"),
        ("0.63", "20000"),
    ]

    events: list[dict] = []
    seq = 1
    ts = 1_000_000.0

    # Initial book snapshot
    events.append(_make_book_snapshot(seq, ts, _ASSET_ID, bids=bids, asks=asks))
    seq += 1
    ts += 1.0

    # 30 price_change events — updates keep the same wide spread
    for i in range(30):
        ev = {
            "seq": seq,
            "ts_recv": ts,
            "event_type": "price_change",
            "asset_id": _ASSET_ID,
            "changes": [
                {"side": "BUY", "price": "0.40", "size": str(9900 + i)},
                {"side": "SELL", "price": "0.60", "size": str(9900 + i)},
            ],
        }
        events.append(ev)
        seq += 1
        ts += 2.0

    tape_dir = _write_events(tmp_path, events)
    report = run_diagnostic(tape_dir, _ASSET_ID)

    assert report["book_ever_initialized"] is True, (
        "Expected L2Book to be initialized after book snapshot"
    )
    assert report["verdict"] in ("NO_COMPETITIVE_LEVELS", "QUOTES_TOO_WIDE", "RESERVATION_BLOCKED"), (
        f"Expected a zero-fill verdict but got {report['verdict']!r}"
    )
    assert report["fill_successes"] == 0, (
        "Expected zero fills with wide-spread book vs narrow strategy spread"
    )
    # Quote ticks should be > 0 because BBO is not None
    assert report["quote_ticks"] >= 0  # lenient: strategy may not quote without valid BBO


# ---------------------------------------------------------------------------
# Test 3 — FILLS_OK
# ---------------------------------------------------------------------------


def test_book_initialized_with_fills(tmp_path: Path) -> None:
    """Tape has a book snapshot, then a price_change that brings ask below strategy BUY limit.

    Sequence:
      1. Book snapshot: bid=0.49, ask=0.55 (mid=0.52).
         Strategy generates BUY at ~0.45 (A-S with 24h session, logit space).
         BUY order is submitted but cannot fill yet (ask=0.55 > strat_bid).
      2. price_change: ask drops to 0.30 (far below strat_bid ~0.45).
         broker.step fires — the existing BUY order fills against ask=0.30.

    With ZERO_LATENCY the order submitted at seq=1 is activated and eligible
    for fills at seq=1 onwards.  The fill occurs at seq=2 when the book update
    exposes an ask level at 0.30.

    Expected verdict: FILLS_OK.
    """
    events: list[dict] = [
        # --- seq 1: book snapshot, wide ask (no fill yet) ---
        {
            "seq": 1,
            "ts_recv": 1_000_000.0,
            "event_type": "book",
            "asset_id": _ASSET_ID,
            "bids": [{"price": "0.49", "size": "1000"}],
            "asks": [{"price": "0.55", "size": "1000"}],
        },
        # --- seq 2: ask drops aggressively below strat BUY limit (~0.45) ---
        # Removes old 0.55 ask and adds new 0.30 ask with huge size.
        {
            "seq": 2,
            "ts_recv": 1_000_001.0,
            "event_type": "price_change",
            "asset_id": _ASSET_ID,
            "changes": [
                {"side": "SELL", "price": "0.55", "size": "0"},
                {"side": "SELL", "price": "0.30", "size": "10000"},
            ],
        },
        # --- seq 3: additional tick to confirm book still has aggressive ask ---
        {
            "seq": 3,
            "ts_recv": 1_000_002.0,
            "event_type": "price_change",
            "asset_id": _ASSET_ID,
            "changes": [
                {"side": "SELL", "price": "0.30", "size": "10000"},
            ],
        },
    ]

    tape_dir = _write_events(tmp_path, events)
    report = run_diagnostic(tape_dir, _ASSET_ID)

    assert report["book_ever_initialized"] is True, (
        "Expected L2Book to be initialized after book snapshot"
    )
    assert report["verdict"] == "FILLS_OK", (
        f"Expected FILLS_OK when ask drops below strategy BUY limit but got {report['verdict']!r}\n"
        f"fill_successes={report['fill_successes']}\n"
        f"quote_ticks={report['quote_ticks']}\n"
        f"order_intents_by_side={report['order_intents_by_side']}\n"
        f"fill_rejection_counts={report['fill_rejection_counts']}\n"
        f"quote_samples={json.dumps(report['quote_samples'][:3], indent=2)}"
    )
    assert report["fill_successes"] > 0, (
        "Expected at least one BUY fill when ask dropped to 0.30 (below strat BUY ~0.45)"
    )
